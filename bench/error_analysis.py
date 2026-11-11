"""Group the failures of the single test run into categories.

Counts are computed from results/test/*.jsonl. Only the "fix" texts are written by hand.
WhyBot itself failed on very few test scenarios, so the analysis also covers the two
baselines and WhyBot's claims that the judge did not accept.

Run:  python -m bench.error_analysis   -> results/error_analysis.json
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from whybot.config import REPO_ROOT

TEST = REPO_ROOT / "results" / "test"
Record = dict[str, Any]


def top_type(r: Record) -> str | None:
    causes = r["report"]["causes"]
    return causes[0]["cause_type"] if causes else None


def wrong(r: Record) -> bool:
    return not r["scores"]["correct_at_1"]


# (system, category, test, fix)
RULES: list[tuple[str, str, Callable[[Record], bool], str]] = [
    (
        "whybot",
        "WhyBot: verifier dropped a correct cause, so the answer became 'not enough evidence'",
        lambda r: wrong(r) and not r["expected_abstain"] and r["scores"]["abstained"],
        "Let the verifier return 'partly supported' and keep the supported part of a claim. Ask the ranker for one fact per claim so one wrong detail does not sink the cause.",
    ),
    (
        "whybot",
        "WhyBot: right answer, but at least one kept claim was rejected by the judge",
        lambda r: not wrong(r) and bool(r.get("judge")) and r["judge"]["faithful"] < r["judge"]["claims"],
        "Use the stronger model for verification, or verify each claim in its own call. Check the 30 hand labels first: some of these are judge strictness, not real errors.",
    ),
    (
        "rag",
        "RAG: abstained although documents explained the move (the key documents were not in the top 8)",
        lambda r: wrong(r) and not r["expected_abstain"] and r["scores"]["abstained"],
        "Search with a date filter and with queries built from the affected segment, not the raw question. This is what the agent's tools do.",
    ),
    (
        "rag",
        "RAG: named a cause, but the wrong one or the wrong segment",
        lambda r: wrong(r) and not r["expected_abstain"] and not r["scores"]["abstained"],
        "Give the model metric tools so it can check which segment moved before trusting a document.",
    ),
    (
        "llm_only",
        "LLM only: guessed the wrong cause type",
        lambda r: wrong(r) and not r["expected_abstain"] and top_type(r) != r["expected"]["cause_type"],
        "No fix without data. A model that sees only the question can only guess the most common cause.",
    ),
    (
        "llm_only",
        "LLM only: right cause type, wrong segment",
        lambda r: wrong(r) and not r["expected_abstain"] and top_type(r) == r["expected"]["cause_type"],
        "Needs the segment breakdown from the metrics. The question alone rarely names the segment.",
    ),
    (
        "llm_only",
        "LLM only: answered a question that has no supporting evidence",
        lambda r: wrong(r) and r["expected_abstain"],
        "Abstain rules need evidence to check against. Without retrieval the model cannot know that nothing explains the move.",
    ),
]


def main() -> None:
    records = {
        system: [json.loads(line) for line in open(TEST / f"{system}.jsonl")]
        for system in {rule[0] for rule in RULES}
    }
    rows = []
    for system, category, test, fix in RULES:
        hits = [r["scenario_id"] for r in records[system] if "scores" in r and test(r)]
        rows.append({"category": category, "count": len(hits), "example_ids": hits[:4], "fix": fix})
        print(f"{len(hits):3d}  {category}")
    (REPO_ROOT / "results" / "error_analysis.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
