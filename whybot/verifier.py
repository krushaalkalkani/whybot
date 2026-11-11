"""Citation verifier: checks that every claim is backed by the evidence it cites.

Two passes:
  1. Code check (free, exact): the cited IDs must be evidence this run actually
     retrieved, and must not be quarantined. This catches made-up IDs.
  2. LLM check: a separate call reads each claim next to the cited text and answers
     supported / not supported. This catches claims that cite a real document which
     does not say what the claim says.

Claims that fail are removed from the answer and listed under "dropped claims".
"""

from __future__ import annotations

from whybot.llm import LLM, LLMResult
from whybot.prompts import VERIFY_SYSTEM, render_evidence
from whybot.schemas import Cause, DraftCause, EvidenceCard, VerifiedClaim, VerifierOutput


def usable_ids(evidence_ids: list[str], evidence: dict[str, EvidenceCard]) -> list[str]:
    return [eid for eid in evidence_ids if eid in evidence and not evidence[eid].quarantined]


def without_verifier(drafts: list[DraftCause]) -> list[Cause]:
    """Used by the 'no verifier' ablation and the baselines: keep every claim, unchecked."""
    return [
        Cause(
            rank=i,
            cause_type=d.cause_type,
            segment_dimension=d.segment_dimension,
            segment_value=d.segment_value,
            title=d.title,
            confidence=d.confidence,
            claims=[VerifiedClaim(text=c.text, evidence_ids=c.evidence_ids, verified=None) for c in d.claims],
        )  # fmt: skip
        for i, d in enumerate(drafts, start=1)
    ]


def verify(
    llm: LLM, model: str, effort: str, drafts: list[DraftCause], evidence: dict[str, EvidenceCard]
) -> tuple[list[Cause], list[VerifiedClaim], LLMResult | None]:
    """Return (causes with only supported claims, dropped claims, the LLM call or None)."""
    dropped: list[VerifiedClaim] = []
    to_check: list[tuple[int, int, list[str]]] = []  # (cause index, claim index, usable ids)

    # Pass 1: code check.
    for ci, draft in enumerate(drafts):
        for ki, claim in enumerate(draft.claims):
            ids = usable_ids(claim.evidence_ids, evidence)
            if ids:
                to_check.append((ci, ki, ids))
            else:
                dropped.append(
                    VerifiedClaim(text=claim.text, evidence_ids=claim.evidence_ids, verified=False,
                                  note="Cites no evidence that was retrieved in this run.")
                )  # fmt: skip

    # Pass 2: LLM check, all claims in one call.
    supported: dict[int, tuple[bool, str]] = {}
    result: LLMResult | None = None
    if to_check:
        parts = []
        for number, (ci, ki, ids) in enumerate(to_check, start=1):
            texts = "\n".join(render_evidence(evidence[eid]) for eid in ids)
            parts.append(f"Claim {number}: {drafts[ci].claims[ki].text}\nCited evidence:\n{texts}")
        result = llm.complete(
            model=model, system=VERIFY_SYSTEM, effort=effort, schema=VerifierOutput,
            messages=[{"role": "user", "content": "\n\n---\n\n".join(parts)}],
        )  # fmt: skip
        for check in result.parse(VerifierOutput).checks:
            supported[check.claim_number] = (check.supported, check.reason)

    kept: dict[int, list[VerifiedClaim]] = {ci: [] for ci in range(len(drafts))}
    for number, (ci, ki, ids) in enumerate(to_check, start=1):
        ok, reason = supported.get(number, (False, "The verifier returned no verdict for this claim."))
        checked = VerifiedClaim(text=drafts[ci].claims[ki].text, evidence_ids=ids, verified=ok, note=reason)
        (kept[ci] if ok else dropped).append(checked)

    causes = []
    for ci, draft in enumerate(drafts):
        lost_claims = len(kept[ci]) < len(draft.claims)
        confidence = "medium" if lost_claims and draft.confidence == "high" else draft.confidence
        causes.append(
            Cause(
                rank=ci + 1,
                cause_type=draft.cause_type,
                segment_dimension=draft.segment_dimension,
                segment_value=draft.segment_value,
                title=draft.title,
                confidence=confidence,
                claims=kept[ci],
            )  # fmt: skip
        )
    return causes, dropped, result
