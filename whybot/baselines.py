"""The two baselines WhyBot is compared against.

  A. LLM only:   one call, the question and nothing else.
  B. Plain RAG:  embed the question, take the 8 nearest documents (dense only, no date
                 filter, no reranker), one call. No tools, no verifier, no abstain rules.

Both write the same DraftReport as WhyBot's ranker, so one scorer handles all systems.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from whybot.agent import AgentDeps, totals_from_steps
from whybot.config import RetrievalConfig
from whybot.prompts import BASELINE_LLM_ONLY_SYSTEM, BASELINE_RAG_SYSTEM, render_dossier
from whybot.schemas import DraftReport, EvidenceCard, Report, Step
from whybot.verifier import without_verifier

RAG_CONFIG = RetrievalConfig(use_bm25=False, use_dense=True, use_rerank=False)
RAG_TOP_K = 8


def _to_report(
    draft: DraftReport, evidence: dict[str, EvidenceCard], steps: list[Step], started: float
) -> Report:
    """Baselines take the model's answer as it is: nothing is verified or filtered."""
    causes = [] if draft.abstain else without_verifier(draft.causes[:3])
    cited = [eid for cause in causes for claim in cause.claims for eid in claim.evidence_ids]
    return Report(
        verdict="answered" if causes else "insufficient_evidence",
        summary=draft.summary or draft.abstain_reason,
        causes=causes,
        evidence={eid: evidence[eid] for eid in dict.fromkeys(cited) if eid in evidence},
        totals=totals_from_steps(steps, started),
    )


def run_llm_only(question: str, deps: AgentDeps) -> Iterator[Step | Report]:
    started = time.time()
    result = deps.llm.complete(
        model=deps.model, system=BASELINE_LLM_ONLY_SYSTEM, effort=deps.effort, schema=DraftReport,
        messages=[{"role": "user", "content": question}],
    )  # fmt: skip
    draft = result.parse(DraftReport)
    step = Step(
        index=0, kind="rank", name="llm_only", title="Answer from the question alone", output=draft.model_dump(),
        latency_ms=result.latency_ms, input_tokens=result.input_tokens, output_tokens=result.output_tokens, cost_usd=result.cost_usd,
    )  # fmt: skip
    yield step
    yield _to_report(draft, {}, [step], started)


def run_rag(question: str, deps: AgentDeps) -> Iterator[Step | Report]:
    started = time.time()
    cards = deps.ctx.retriever.search(question, RAG_CONFIG, k=RAG_TOP_K)
    evidence = {card.id: card for card in cards}
    search_step = Step(
        index=0, kind="tool", name="vector_search", title="Vector search with the question",
        detail=", ".join(evidence), evidence_ids=list(evidence), latency_ms=int((time.time() - started) * 1000),
    )  # fmt: skip
    yield search_step
    result = deps.llm.complete(
        model=deps.model, system=BASELINE_RAG_SYSTEM, effort=deps.effort, schema=DraftReport,
        messages=[{"role": "user", "content": f"Question: {question}\n\nRetrieved documents:\n{render_dossier(cards)}"}],
    )  # fmt: skip
    draft = result.parse(DraftReport)
    answer_step = Step(
        index=1, kind="rank", name="rag_answer", title="Answer from retrieved documents", output=draft.model_dump(),
        latency_ms=result.latency_ms, input_tokens=result.input_tokens, output_tokens=result.output_tokens, cost_usd=result.cost_usd,
    )  # fmt: skip
    yield answer_step
    yield _to_report(draft, evidence, [search_step, answer_step], started)
