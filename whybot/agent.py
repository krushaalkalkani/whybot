"""The WhyBot agent loop: a plain Python state machine. No agent framework.

    PLAN -> TRIAGE -> INVESTIGATE -> RANK -> VERIFY -> GUARD -> DONE

  PLAN         one LLM call: parse the question (metric, date, segment) and list steps
  TRIAGE       code, no LLM: always run detect_anomaly and decompose_by_segment
  INVESTIGATE  the model picks tools in a loop (search, SQL, ...) until it has enough,
               or the tool budget or the time budget runs out
  RANK         one LLM call: write up to 3 causes; every claim cites evidence IDs
  VERIFY       check every claim against its cited evidence; drop unsupported ones
  GUARD        code rules: abstain unless a cause still stands on real evidence

Each handler is a generator. It yields `Step` objects (shown live in the UI and stored
with the run) and returns the next state. `run_whybot` yields the steps, then the Report.
"""

from __future__ import annotations

import time
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

import psycopg
from pydantic import BaseModel, ValidationError

from whybot.config import AgentConfig
from whybot.guardrails import apply_abstain_rules, quarantine_if_suspicious
from whybot.llm import LLM, LLMResult
from whybot.prompts import INVESTIGATE_SYSTEM, PLAN_SYSTEM, RANK_SYSTEM, render_dossier
from whybot.schemas import (
    AnomalyOutput,
    Cause,
    DecomposeOutput,
    DraftReport,
    EvidenceCard,
    MetricQueryOutput,
    Plan,
    Report,
    SearchOutput,
    Step,
    Totals,
    VerifiedClaim,
)
from whybot.tools import TOOLS, ToolContext, ToolError
from whybot.verifier import verify, without_verifier

DATA_START, DATA_END = date(2024, 1, 1), date(2025, 12, 31)


class State(Enum):
    PLAN = "plan"
    TRIAGE = "triage"
    INVESTIGATE = "investigate"
    RANK = "rank"
    VERIFY = "verify"
    GUARD = "guard"
    DONE = "done"


@dataclass
class AgentDeps:
    """Everything the agent needs from outside. Tests pass a fake LLM here."""

    llm: LLM
    ctx: ToolContext
    model: str
    effort: str
    config: AgentConfig


@dataclass
class Run:
    """All the state of one investigation."""

    question: str
    started: float = field(default_factory=time.time)
    steps: list[Step] = field(default_factory=list)
    evidence: dict[str, EvidenceCard] = field(default_factory=dict)  # everything retrieved so far, by ID
    plan: Plan | None = None
    draft: DraftReport | None = None
    causes: list[Cause] = field(default_factory=list)
    dropped: list[VerifiedClaim] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metric_results: int = 0
    tool_calls: int = 0


StepGen = Generator[Step, None, State]


class Agent:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    # ------------------------------------------------------------------ the state machine

    def run(self, question: str) -> Iterator[Step | Report]:
        run = Run(question=question)
        handlers = {
            State.PLAN: self._plan,
            State.TRIAGE: self._triage,
            State.INVESTIGATE: self._investigate,
            State.RANK: self._rank,
            State.VERIFY: self._verify,
            State.GUARD: self._guard,
        }
        state = State.PLAN
        while state is not State.DONE:
            state = yield from handlers[state](run)
        yield self._report(run)

    # ------------------------------------------------------------------ PLAN

    def _plan(self, run: Run) -> StepGen:
        result = self.deps.llm.complete(
            model=self.deps.model, system=PLAN_SYSTEM, effort=self.deps.effort, schema=Plan,
            messages=[{"role": "user", "content": run.question}],
        )  # fmt: skip
        plan = result.parse(Plan)
        run.plan = plan
        yield self._llm_step(
            run,
            "plan",
            "plan",
            f"Plan: {plan.metric} on {plan.date}",
            " | ".join(plan.steps),
            result,
            output=plan.model_dump(),
        )
        try:
            in_range = DATA_START <= date.fromisoformat(plan.date) <= DATA_END
        except ValueError:
            in_range = False
        if not in_range:
            run.notes.append(f"The date '{plan.date}' is outside the data (2024-01-01 to 2025-12-31).")
            run.draft = DraftReport(abstain=True, abstain_reason=run.notes[-1], summary="", causes=[])
            return State.GUARD
        return State.TRIAGE

    # ------------------------------------------------------------------ TRIAGE

    def _triage(self, run: Run) -> StepGen:
        """Two checks every investigation needs, run by code so they cannot be skipped."""
        assert run.plan is not None
        plan = run.plan
        filters = {"region": plan.region, "platform": plan.platform, "channel": plan.channel}
        step, _, _ = self._call_tool(
            run, "detect_anomaly", {"metric": plan.metric, "date": plan.date, **filters}
        )
        yield step
        step, _, _ = self._call_tool(run, "decompose_by_segment", {"metric": plan.metric, "date": plan.date})
        yield step
        return State.INVESTIGATE

    # ------------------------------------------------------------------ INVESTIGATE

    def _investigate(self, run: Run) -> StepGen:
        assert run.plan is not None
        config = self.deps.config
        intro = (
            f"Question: {run.question}\n\nPlan:\n"
            + "\n".join(f"- {s}" for s in run.plan.steps)
            + "\n\nTriage results:\n"
            + render_dossier(list(run.evidence.values()))
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": intro}]
        tool_specs = [tool.claude_spec() for tool in TOOLS.values()]

        while True:
            if run.tool_calls >= config.max_tool_calls:
                run.notes.append(f"Stopped investigating: tool budget of {config.max_tool_calls} calls used.")
                break
            if time.time() - run.started > 0.6 * config.timeout_s:
                run.notes.append("Stopped investigating: time budget used.")
                break
            result = self.deps.llm.complete(
                model=self.deps.model, system=INVESTIGATE_SYSTEM, effort=self.deps.effort,
                messages=messages, tools=tool_specs,
            )  # fmt: skip
            calls = result.tool_uses()
            title = "Choose next tools" if calls else "Finished investigating"
            yield self._llm_step(run, "llm", "investigate", title, result.text()[:400], result)
            if not calls:
                break

            # The API needs the assistant turn back unchanged, then one tool_result per tool_use.
            messages.append({"role": "assistant", "content": result.content})
            tool_results = []
            for call in calls:
                step, content, is_error = self._call_tool(run, call["name"], call["input"])
                yield step
                tool_result = {"type": "tool_result", "tool_use_id": call["id"], "content": content}
                if is_error:
                    tool_result["is_error"] = True
                tool_results.append(tool_result)
            messages.append({"role": "user", "content": tool_results})
        return State.RANK

    # ------------------------------------------------------------------ RANK

    def _rank(self, run: Run) -> StepGen:
        content = f"Question: {run.question}\n\nEvidence:\n{render_dossier(list(run.evidence.values()))}"
        result = self.deps.llm.complete(
            model=self.deps.model, system=RANK_SYSTEM, effort=self.deps.effort, schema=DraftReport,
            messages=[{"role": "user", "content": content}],
        )  # fmt: skip
        draft = result.parse(DraftReport)
        draft.causes = draft.causes[:3]
        run.draft = draft
        detail = (
            "Abstain: " + draft.abstain_reason if draft.abstain else "; ".join(c.title for c in draft.causes)
        )
        yield self._llm_step(
            run, "rank", "rank", "Rank hypotheses", detail, result, output=draft.model_dump()
        )
        return State.VERIFY if self.deps.config.use_verifier else State.GUARD

    # ------------------------------------------------------------------ VERIFY

    def _verify(self, run: Run) -> StepGen:
        assert run.draft is not None
        run.causes, run.dropped, result = verify(
            self.deps.llm, self.deps.model, self.deps.effort, run.draft.causes, run.evidence
        )
        kept = sum(len(c.claims) for c in run.causes)
        detail = f"{kept} claims supported, {len(run.dropped)} dropped"
        output = {"kept": kept, "dropped": [c.model_dump() for c in run.dropped]}
        if result is not None:
            yield self._llm_step(run, "verify", "verify", "Verify citations", detail, result, output=output)
        else:
            yield self._add_step(
                run,
                Step(
                    index=0,
                    kind="verify",
                    name="verify",
                    title="Verify citations",
                    detail=detail,
                    output=output,
                ),
            )
        return State.GUARD

    # ------------------------------------------------------------------ GUARD

    def _guard(self, run: Run) -> StepGen:
        assert run.draft is not None
        if not self.deps.config.use_verifier and not run.causes:
            run.causes = without_verifier(run.draft.causes)
        run.causes, notes = apply_abstain_rules(run.draft.abstain, run.causes, run.evidence)
        run.notes += notes
        verdict = "answered" if run.causes else "insufficient_evidence"
        yield self._add_step(
            run,
            Step(
                index=0,
                kind="guard",
                name="guard",
                title=f"Guardrails: {verdict}",
                detail=" ".join(notes),
                output={"verdict": verdict, "notes": notes},
            ),
        )
        return State.DONE

    # ------------------------------------------------------------------ report

    def _report(self, run: Run) -> Report:
        assert run.draft is not None
        answered = bool(run.causes)
        cited = [eid for cause in run.causes for claim in cause.claims for eid in claim.evidence_ids]
        if answered:
            summary = run.draft.summary
        else:
            reason = run.draft.abstain_reason or (run.notes[-1] if run.notes else "")
            summary = f"Not enough evidence to name a cause. {reason}".strip()
        return Report(
            verdict="answered" if answered else "insufficient_evidence",
            summary=summary,
            causes=run.causes,
            evidence={eid: run.evidence[eid] for eid in dict.fromkeys(cited) if eid in run.evidence},
            dropped_claims=run.dropped,
            quarantined_ids=[card.id for card in run.evidence.values() if card.quarantined],
            notes=run.notes,
            totals=totals_from_steps(run.steps, run.started),
        )

    # ------------------------------------------------------------------ helpers

    def _add_step(self, run: Run, step: Step) -> Step:
        step.index = len(run.steps)
        run.steps.append(step)
        return step

    def _llm_step(
        self,
        run: Run,
        kind: Any,
        name: str,
        title: str,
        detail: str,
        result: LLMResult,
        output: dict[str, Any] | None = None,
    ) -> Step:
        return self._add_step(
            run,
            Step(
                index=0,
                kind=kind,
                name=name,
                title=title,
                detail=detail,
                output=output or {},
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
            ),  # fmt: skip
        )

    def _call_tool(self, run: Run, name: str, raw_input: dict[str, Any]) -> tuple[Step, str, bool]:
        """Validate the input, run the tool, record evidence. Returns (step, text for the model, is_error)."""
        started = time.time()
        run.tool_calls += 1
        clean_input = {k: v for k, v in raw_input.items() if v is not None}
        output: BaseModel | None = None
        try:
            if name not in TOOLS:
                raise ToolError(f"Unknown tool '{name}'.")
            if run.tool_calls > self.deps.config.max_tool_calls + 2:  # +2: triage calls are free
                raise ToolError("Tool budget used up. Write your conclusion now.")
            tool = TOOLS[name]
            output = tool.run(tool.input_model.model_validate(clean_input), self.deps.ctx)
        except ValidationError as error:
            message = f"Invalid input for {name}: {error.errors()[0]['msg']} at {error.errors()[0]['loc']}"
        except (ToolError, ValueError) as error:  # SqlRejected is a ValueError
            message = str(error)
        except psycopg.Error as error:
            message = f"Database error: {str(error).splitlines()[0]}"

        latency_ms = int((time.time() - started) * 1000)
        if output is None:
            step = Step(
                index=0,
                kind="tool",
                name=name,
                title=f"{name} failed",
                detail=message,
                input=clean_input,
                is_error=True,
                latency_ms=latency_ms,
            )
            return self._add_step(run, step), message, True

        cards = self._evidence_from(run, name, clean_input, output)
        for card in cards:
            run.evidence.setdefault(card.id, card)
        content = render_dossier(cards) if cards else "No documents found."
        step = Step(
            index=0, kind="tool", name=name, title=tool_title(name, clean_input), detail=tool_detail(output),
            input=clean_input, output=trimmed(output), evidence_ids=[c.id for c in cards], latency_ms=latency_ms,
        )  # fmt: skip
        return self._add_step(run, step), content, False

    def _evidence_from(
        self, run: Run, name: str, tool_input: dict[str, Any], output: BaseModel
    ) -> list[EvidenceCard]:
        """Turn a tool output into evidence cards. Search results are screened for injections."""
        if isinstance(output, SearchOutput):
            return [quarantine_if_suspicious(card) for card in output.results]
        run.metric_results += 1
        day = str(tool_input.get("date", run.plan.date if run.plan else ""))
        return [
            EvidenceCard(
                id=f"M{run.metric_results}",
                source="metric",
                title=tool_title(name, tool_input),
                date=day,
                body=metric_text(tool_input, output),
                meta={"tool": name},
            )  # fmt: skip
        ]


# ---------------------------------------------------------------------- formatting helpers


def tool_title(name: str, tool_input: dict[str, Any]) -> str:
    if name == "search_evidence":
        return f"Search evidence: {tool_input.get('query', '')}"
    if name == "run_metric_query":
        return "Run metric query"
    filters = ", ".join(
        f"{k}={tool_input[k]}" for k in ("region", "platform", "channel") if tool_input.get(k)
    )
    return f"{name}: {tool_input.get('metric', '')} on {tool_input.get('date', '')}" + (
        f" ({filters})" if filters else ""
    )


def tool_detail(output: BaseModel) -> str:
    if isinstance(output, SearchOutput):
        return f"{len(output.results)} documents: " + ", ".join(card.id for card in output.results)
    if isinstance(output, AnomalyOutput | DecomposeOutput):
        return output.explanation
    if isinstance(output, MetricQueryOutput):
        return f"{output.row_count} rows"
    return ""


def metric_text(tool_input: dict[str, Any], output: BaseModel) -> str:
    """Metric tool output as text, used as the body of an M-evidence card."""
    if isinstance(output, AnomalyOutput):
        return output.explanation
    if isinstance(output, DecomposeOutput):
        lines = [output.explanation, "Change vs weekday baseline, per slice:"]
        lines += [
            f"  {s.dimension}={s.value}: {s.pct_change:+.1f}% (z {s.z_score:+.1f})" for s in output.segments
        ]
        return "\n".join(lines)
    if isinstance(output, MetricQueryOutput):
        lines = [f"SQL: {tool_input.get('sql', '')}", " | ".join(output.columns)]
        lines += [" | ".join(str(v) for v in row) for row in output.rows[:40]]
        if output.row_count > 40:
            lines.append(f"... {output.row_count - 40} more rows")
        return "\n".join(lines)
    return output.model_dump_json()


def trimmed(output: BaseModel) -> dict[str, Any]:
    """Tool output for the trace, with long lists cut so stored runs stay small."""
    data = output.model_dump()
    if isinstance(output, MetricQueryOutput):
        data["rows"] = data["rows"][:40]
    if isinstance(output, SearchOutput):
        data["results"] = [
            {"id": c.id, "title": c.title, "date": c.date, "score": c.score} for c in output.results
        ]
    return data


def totals_from_steps(steps: list[Step], started: float) -> Totals:
    return Totals(
        latency_ms=int((time.time() - started) * 1000),
        input_tokens=sum(s.input_tokens for s in steps),
        output_tokens=sum(s.output_tokens for s in steps),
        cost_usd=round(sum(s.cost_usd for s in steps), 6),
        llm_calls=sum(1 for s in steps if s.input_tokens > 0),
        tool_calls=sum(1 for s in steps if s.kind == "tool"),
    )


def run_whybot(question: str, deps: AgentDeps) -> Iterator[Step | Report]:
    return Agent(deps).run(question)


def collect(events: Iterator[Step | Report]) -> tuple[Report, list[Step]]:
    """Run an agent to the end. Used by the eval harness and the tests."""
    steps: list[Step] = []
    report: Report | None = None
    for event in events:
        if isinstance(event, Report):
            report = event
        else:
            steps.append(event)
    assert report is not None
    return report, steps
