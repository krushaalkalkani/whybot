"""Example questions for the demo, served from stored runs at zero cost.

  python -m bench.examples --make   run WhyBot on a few dev scenarios, save results/examples/*.json
  python -m bench.examples --load   insert the saved runs into the database (API cache)

Only dev scenarios are used, never the test split.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from bench.load import read_scenarios
from whybot import store
from whybot.agent import AgentDeps, collect, run_whybot
from whybot.config import REPO_ROOT, AgentConfig, get_settings
from whybot.db import connect
from whybot.llm import ClaudeLLM
from whybot.retrieval.search import Retriever
from whybot.schemas import RunRecord
from whybot.tools import ToolContext

OUT = REPO_ROOT / "results" / "examples"
# scenario id -> short tag shown in the UI
PICKS = {
    "S001": "Payment provider error",
    "S015": "Bad deploy",
    "S020": "Campaign ended",
    "S002": "Decoy: weekend dip",
    "S012": "No evidence: abstains",
    "S004": "Prompt injection in tickets",
}


def make() -> None:
    settings = get_settings()
    conn = connect(settings.database_url)
    ctx = ToolContext(
        conn,
        connect(settings.database_url_readonly),
        Retriever(conn, settings.models_dir),
        AgentConfig().retrieval,
    )
    llm = ClaudeLLM(cache_dir=REPO_ROOT / "bench" / "cache" / "live")
    deps = AgentDeps(llm, ctx, settings.agent_model, settings.agent_effort, AgentConfig())
    scenarios = {s["id"]: s for s in read_scenarios("dev")}
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for scenario_id, tag in PICKS.items():
        question = scenarios[scenario_id]["question"]
        report, steps = collect(run_whybot(question, deps))
        report.totals.latency_ms = sum(
            s.latency_ms for s in steps
        )  # recorded latency, also right on a cached replay
        record = RunRecord(id=f"ex-{scenario_id}", created_at=datetime.now(UTC).isoformat(), question=question,
                           system="whybot", status="done", steps=steps, report=report)  # fmt: skip
        (OUT / f"{record.id}.json").write_text(record.model_dump_json(indent=1) + "\n")
        index.append({"id": record.id, "question": question, "tag": tag})
        print(record.id, report.verdict, [c.cause_type for c in report.causes])
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")


def load() -> None:
    files = sorted(Path(OUT).glob("ex-*.json")) if OUT.exists() else []
    conn = connect(get_settings().database_url)
    for path in files:
        store.save_run(conn, RunRecord.model_validate_json(path.read_text()), is_example=True)
    print(f"loaded {len(files)} example runs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--make", action="store_true")
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    if args.make:
        make()
    if args.load:
        load()
