"""Agent loop tests. The LLM is scripted (FakeLLM); the metric tools hit the real benchmark data."""

from __future__ import annotations

from typing import Any

import pytest

from tests.fakes import FakeLLM, FakeRetriever, text_reply, tool_reply
from whybot.agent import AgentDeps, collect, run_whybot
from whybot.baselines import run_llm_only
from whybot.config import AgentConfig, RetrievalConfig
from whybot.db import Conn
from whybot.schemas import EvidenceCard, Report, Step
from whybot.tools import ToolContext

pytestmark = pytest.mark.db

QUESTION = "What caused the 40% fall in checkout conversion on 2024-06-10?"
PLAN = {"metric": "conversion_rate", "date": "2024-06-10", "direction": "drop", "region": None, "platform": None,
        "channel": None, "steps": ["check anomaly", "search changelog"]}  # fmt: skip
ISSUE = EvidenceCard(id="ISS-0100", source="issue", title="Place order returns HTTP 500 since checkout-service v4.1.0",
                     date="2024-06-10", body="Error rate went up after the rollout.")  # fmt: skip


def cause(ids: list[str], confidence: str = "high", cause_type: str = "bad_deploy") -> dict[str, Any]:
    return {"cause_type": cause_type, "segment_dimension": "all", "segment_value": "all", "title": "Bad checkout deploy",
            "confidence": confidence, "claims": [{"text": "A deploy broke place order.", "evidence_ids": ids}]}  # fmt: skip


def draft(causes: list[dict[str, Any]], abstain: bool = False) -> dict[str, Any]:
    return {
        "abstain": abstain,
        "abstain_reason": "nothing found" if abstain else "",
        "summary": "A deploy broke checkout.",
        "causes": causes,
    }


def deps(
    conn: Conn, readonly_conn: Conn, llm: FakeLLM, cards: list[EvidenceCard], **config: Any
) -> AgentDeps:
    ctx = ToolContext(conn, readonly_conn, FakeRetriever(cards), RetrievalConfig())  # type: ignore[arg-type]
    return AgentDeps(llm, ctx, "claude-haiku-5-5", "medium", AgentConfig(**config))


def run(agent_deps: AgentDeps, question: str = QUESTION) -> tuple[Report, list[Step]]:
    return collect(run_whybot(question, agent_deps))


def test_happy_path_walks_every_state(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([
        text_reply(PLAN),
        tool_reply(("search_evidence", {"query": "checkout error", "date_from": "2024-06-08", "date_to": "2024-06-12"})),
        text_reply("Enough evidence."),
        text_reply(draft([cause(["ISS-0100", "M1"])])),
        text_reply({"checks": [{"claim_number": 1, "supported": True, "reason": "The issue says so."}]}),
    ])  # fmt: skip
    report, steps = run(deps(conn, readonly_conn, llm, [ISSUE]))
    assert [s.kind for s in steps] == [
        "plan",
        "tool",
        "tool",
        "llm",
        "tool",
        "llm",
        "rank",
        "verify",
        "guard",
    ]
    assert report.verdict == "answered" and report.causes[0].claims[0].verified is True
    assert set(report.evidence) == {"ISS-0100", "M1"} and report.evidence["M1"].source == "metric"
    assert report.totals.tool_calls == 3 and report.totals.llm_calls == 5 and report.totals.cost_usd > 0
    # The tool result went back to the model as one user message with a matching tool_use_id.
    last_investigate_request = llm.requests[2]
    assert last_investigate_request["messages"][-1]["content"][0]["tool_use_id"] == "toolu_0"


def test_made_up_citation_is_dropped_and_agent_abstains(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM(
        [text_reply(PLAN), text_reply("Nothing to search."), text_reply(draft([cause(["ISS-9999"])]))]
    )
    report, steps = run(deps(conn, readonly_conn, llm, []))
    assert report.verdict == "insufficient_evidence" and report.causes == []
    assert report.dropped_claims[0].evidence_ids == ["ISS-9999"]
    assert steps[-2].kind == "verify" and llm.replies == []  # no LLM verify call was needed


def test_cause_with_only_metric_evidence_is_not_enough(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([
        text_reply(PLAN), text_reply("Done."), text_reply(draft([cause(["M1"])])),
        text_reply({"checks": [{"claim_number": 1, "supported": True, "reason": "ok"}]}),
    ])  # fmt: skip
    report, _ = run(deps(conn, readonly_conn, llm, []))
    assert report.verdict == "insufficient_evidence" and "no document supports it" in " ".join(report.notes)


def test_seasonality_needs_only_metric_evidence(conn: Conn, readonly_conn: Conn) -> None:
    plan = {**PLAN, "metric": "sessions", "date": "2024-03-02"}
    llm = FakeLLM([
        text_reply(plan), text_reply("Normal Saturday."), text_reply(draft([cause(["M1"], cause_type="seasonality")])),
        text_reply({"checks": [{"claim_number": 1, "supported": True, "reason": "ok"}]}),
    ])  # fmt: skip
    report, _ = run(
        deps(conn, readonly_conn, llm, []),
        "Why did sessions drop 17% on 2024-03-02 compared with the day before?",
    )
    assert report.verdict == "answered" and report.causes[0].cause_type == "seasonality"


def test_low_confidence_and_ranker_abstain_both_abstain(conn: Conn, readonly_conn: Conn) -> None:
    ok = text_reply({"checks": [{"claim_number": 1, "supported": True, "reason": "ok"}]})
    llm = FakeLLM(
        [
            text_reply(PLAN),
            text_reply("Done."),
            text_reply(draft([cause(["M1", "M2"], confidence="low")])),
            ok,
        ]
    )
    assert run(deps(conn, readonly_conn, llm, []))[0].verdict == "insufficient_evidence"
    llm = FakeLLM([text_reply(PLAN), text_reply("Done."), text_reply(draft([], abstain=True))])
    report, _ = run(deps(conn, readonly_conn, llm, []))
    assert report.verdict == "insufficient_evidence" and "nothing found" in report.summary


def test_no_verifier_ablation_keeps_claims_unverified(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([
        text_reply(PLAN), tool_reply(("search_evidence", {"query": "checkout"})), text_reply("Done."),
        text_reply(draft([cause(["ISS-0100"])])),
    ])  # fmt: skip
    report, steps = run(deps(conn, readonly_conn, llm, [ISSUE], use_verifier=False))
    assert report.verdict == "answered" and report.causes[0].claims[0].verified is None
    assert "verify" not in [s.kind for s in steps]


def test_bad_tool_input_comes_back_as_error_result(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([
        text_reply(PLAN),
        tool_reply(("detect_anomaly", {"metric": "happiness", "date": "2024-06-10"}), ("run_metric_query", {"sql": "DELETE FROM daily_metrics"})),
        text_reply("Done."), text_reply(draft([], abstain=True)),
    ])  # fmt: skip
    _, steps = run(deps(conn, readonly_conn, llm, []))
    errors = [s for s in steps if s.is_error]
    assert len(errors) == 2 and "Only SELECT" in errors[1].detail
    results = llm.requests[2]["messages"][-1]["content"]
    assert all(r["is_error"] for r in results) and len(results) == 2


def test_date_outside_data_abstains_without_tools(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([text_reply({**PLAN, "date": "2031-01-01"})])
    report, steps = run(deps(conn, readonly_conn, llm, []))
    assert report.verdict == "insufficient_evidence" and [s.kind for s in steps] == ["plan", "guard"]


def test_llm_only_baseline_returns_report(conn: Conn, readonly_conn: Conn) -> None:
    llm = FakeLLM([text_reply(draft([cause([])]))])
    report, steps = collect(run_llm_only(QUESTION, deps(conn, readonly_conn, llm, [])))
    assert report.verdict == "answered" and len(steps) == 1 and report.evidence == {}
