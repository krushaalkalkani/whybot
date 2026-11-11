"""Guardrails: rules in plain code that do not depend on the model behaving well.

1. Prompt-injection filter: documents that look like instructions are quarantined.
   Their text is withheld from the model and they cannot be cited.
2. Abstain rules: the final answer must rest on verified evidence, or WhyBot says
   "not enough evidence".

The filter is a first layer only. It catches known phrasings. Attacks without trigger
words pass through, and then the prompt rules and the citation verifier have to hold.
The benchmark has both kinds so the eval shows how each layer does.
"""

from __future__ import annotations

import re

from whybot.schemas import Cause, EvidenceCard

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts|messages)",
    r"disregard (all |any )?(the )?(previous|prior|above|other) (instructions|evidence|context|messages)",
    r"(^|\n)\s*(system|assistant|developer)\s*:",
    r"new instructions",
    r"you are now (in|a|an) ",
    r"(reveal|print|show|repeat) (your |the )?(system prompt|hidden instructions)",
    r"</?\s*(evidence|system|instructions)\s*>",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)


def looks_like_injection(text: str) -> bool:
    return _INJECTION_RE.search(text) is not None


def quarantine_if_suspicious(card: EvidenceCard) -> EvidenceCard:
    """Mark a document as quarantined when its text matches an injection pattern."""
    if card.source != "metric" and looks_like_injection(f"{card.title}\n{card.body}"):
        return card.model_copy(update={"quarantined": True})
    return card


def apply_abstain_rules(
    ranker_abstained: bool, causes: list[Cause], evidence: dict[str, EvidenceCard]
) -> tuple[list[Cause], list[str]]:
    """Decide which causes survive. Returns (kept causes, notes). No causes left = abstain.

    A cause is kept only if it still has a claim that cites a real document.
    Seasonality is the exception: it is shown by metric evidence, not by a document.
    """
    notes: list[str] = []
    if ranker_abstained:
        return [], ["The model judged the evidence too weak to name a cause."]
    kept: list[Cause] = []
    for cause in causes:
        cited = {eid for claim in cause.claims for eid in claim.evidence_ids if eid in evidence}
        has_document = any(evidence[eid].source != "metric" for eid in cited)
        has_metric = any(evidence[eid].source == "metric" for eid in cited)
        if not cause.claims:
            notes.append(f"Dropped '{cause.title}': none of its claims passed verification.")
        elif cause.cause_type == "seasonality" and not has_metric:
            notes.append(f"Dropped '{cause.title}': seasonality needs metric evidence.")
        elif cause.cause_type != "seasonality" and not has_document:
            notes.append(f"Dropped '{cause.title}': no document supports it.")
        else:
            kept.append(cause)
    if kept and kept[0].confidence == "low":
        notes.append("The top cause had low confidence, so WhyBot does not name a cause.")
        return [], notes
    return [cause.model_copy(update={"rank": i}) for i, cause in enumerate(kept, start=1)], notes
