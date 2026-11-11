"""Run the benchmark. Every number in the README, the site and the resume comes from here.

  python -m bench.run_eval --split dev                       all 7 systems on the 40 dev scenarios
  python -m bench.run_eval --split dev --smoke --systems whybot --no-judge --replay \
        --cache-dir bench/cache/smoke                        the CI gate run (no API calls)
  python -m bench.run_eval --split test                      the single frozen test run

Outputs, under results/<split>[_smoke]/:
  <system>.jsonl   one record per scenario (answer, scores, cost, latency)
  metrics.json     one metrics row per system
The test split refuses to run twice unless you pass --force, so it cannot be tuned on.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from bench.judge import judge_report
from bench.load import read_scenarios
from bench.metrics import aggregate, score_scenario
from whybot.agent import AgentDeps, collect, run_whybot
from whybot.baselines import run_llm_only, run_rag
from whybot.config import REPO_ROOT, AgentConfig, RetrievalConfig, get_settings
from whybot.db import connect
from whybot.llm import ClaudeLLM
from whybot.retrieval.search import Retriever
from whybot.schemas import Report, Step
from whybot.tools import ToolContext

Runner = Callable[[str, AgentDeps], Iterator[Step | Report]]
FULL = AgentConfig()

# name -> (label, group, runner, agent config)
SYSTEMS: dict[str, tuple[str, str, Runner, AgentConfig]] = {
    "llm_only": ("A. LLM only", "main", run_llm_only, FULL),
    "rag": ("B. Vector RAG, no tools", "main", run_rag, FULL),
    "whybot": ("C. WhyBot (full)", "main", run_whybot, FULL),
    "whybot_no_rerank": (
        "C without reranker",
        "ablation",
        run_whybot,
        replace(FULL, retrieval=RetrievalConfig(use_rerank=False)),
    ),
    "whybot_no_verifier": ("C without verifier", "ablation", run_whybot, replace(FULL, use_verifier=False)),
    "whybot_bm25_only": (
        "C with BM25 only",
        "ablation",
        run_whybot,
        replace(FULL, retrieval=RetrievalConfig(use_dense=False)),
    ),
    "whybot_dense_only": (
        "C with dense only",
        "ablation",
        run_whybot,
        replace(FULL, retrieval=RetrievalConfig(use_bm25=False)),
    ),
}
RESULTS_DIR = REPO_ROOT / "results"


class Workers:
    """Gives each thread its own database connections. The models and the BM25 index are shared."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.local = threading.local()
        self.shared = Retriever(connect(self.settings.database_url), self.settings.models_dir)
        self.shared.share(self.shared.conn)  # loads the index and both models once, before the threads start

    def context(self, retrieval: RetrievalConfig) -> ToolContext:
        if not hasattr(self.local, "conn"):
            self.local.conn = connect(self.settings.database_url)
            self.local.readonly = connect(self.settings.database_url_readonly)
            self.local.retriever = self.shared.share(self.local.conn)
        return ToolContext(self.local.conn, self.local.readonly, self.local.retriever, retrieval)


def run_one(
    system: str, scenario: dict[str, Any], workers: Workers, llm: ClaudeLLM, use_judge: bool
) -> dict[str, Any]:
    _, _, runner, config = SYSTEMS[system]
    settings = workers.settings
    record: dict[str, Any] = {
        "scenario_id": scenario["id"],
        "kind": scenario["kind"],
        "system": system,
        "question": scenario["question"],
        "expected": scenario["expected"],
        "expected_abstain": scenario["expected"]["abstain"],
    }
    try:
        deps = AgentDeps(
            llm, workers.context(config.retrieval), settings.agent_model, settings.agent_effort, config
        )
        report, steps = collect(runner(scenario["question"], deps))
        record["scores"] = score_scenario(scenario, report, steps)
        record["judge"] = judge_report(llm, settings.judge_model, report) if use_judge else None
        record["report"] = report.model_dump()
        record["steps"] = [
            {"kind": s.kind, "name": s.name, "title": s.title, "input": s.input, "is_error": s.is_error,
             "latency_ms": s.latency_ms, "input_tokens": s.input_tokens, "output_tokens": s.output_tokens}
            for s in steps
        ]  # fmt: skip
    except Exception as error:  # one failed scenario must not stop the whole eval
        record["error"] = f"{type(error).__name__}: {error}"
    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--smoke", action="store_true", help="only the 20-scenario smoke subset (dev)")
    parser.add_argument("--systems", default="all", help="all | main | comma-separated names")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--replay", action="store_true", help="never call the API; fail on a cache miss")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "bench" / "cache" / "live"))
    parser.add_argument("--out", default="", help="output folder (default results/<split>[_smoke])")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--force", action="store_true", help="allow re-running the frozen test split")
    args = parser.parse_args()

    names = (
        list(SYSTEMS)
        if args.systems == "all"
        else [n for n in SYSTEMS if SYSTEMS[n][1] == "main"]
        if args.systems == "main"
        else args.systems.split(",")
    )
    out_dir = Path(args.out) if args.out else RESULTS_DIR / (args.split + ("_smoke" if args.smoke else ""))
    if args.split == "test" and (out_dir / "metrics.json").exists() and not args.force:
        raise SystemExit(
            "The test split has already been run. It is frozen; use --force only with a written reason."
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = read_scenarios(args.split, smoke=args.smoke)
    workers = Workers()
    llm = ClaudeLLM(cache_dir=Path(args.cache_dir), replay_only=args.replay)
    metrics_path = out_dir / "metrics.json"
    all_metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {"systems": {}}

    for name in names:
        started = time.time()
        with ThreadPoolExecutor(max_workers=args.threads) as pool:
            records = list(
                pool.map(lambda s, name=name: run_one(name, s, workers, llm, not args.no_judge), scenarios)
            )
        with open(out_dir / f"{name}.jsonl", "w") as f:
            for record in records:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        row = aggregate(records)
        all_metrics["systems"][name] = {"label": SYSTEMS[name][0], "group": SYSTEMS[name][1], "metrics": row}
        failed = [r["scenario_id"] + ": " + r["error"] for r in records if "error" in r]
        print(f"{name:20s} acc@1={row['accuracy_at_1']} acc@3={row['accuracy_at_3']} cit_p={row['citation_precision']} "
              f"abst={row['abstention_accuracy']} errors={row['errors']} ({time.time() - started:.0f}s)")  # fmt: skip
        for line in failed[:3]:
            print("   ", line[:200])

    all_metrics.update(
        {
            "split": args.split,
            "smoke": args.smoke,
            "n": len(scenarios),
            "run_date": str(date.today()),
            "agent_model": workers.settings.agent_model,
            "judge_model": None if args.no_judge else workers.settings.judge_model,
            "agent_effort": workers.settings.agent_effort,
        }
    )
    metrics_path.write_text(json.dumps(all_metrics, indent=2, sort_keys=True) + "\n")
    print(f"wrote {metrics_path}")


if __name__ == "__main__":
    main()
