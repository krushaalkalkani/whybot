"""Collect every result file into results/summary.json.

The README tables, the Evals page and docs/RESUME.md are all generated from this one
file. A section that has not been run yet is null, and renders as "not run yet".

Run:  python -m bench.summarize
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from whybot.config import REPO_ROOT

RESULTS = REPO_ROOT / "results"
MANIFEST = REPO_ROOT / "bench" / "data" / "v1" / "MANIFEST.json"
TABLE_METRICS = [
    "accuracy_at_1", "accuracy_at_3", "citation_precision", "citation_recall", "faithfulness", "abstention_accuracy",
    "injection_resistance", "latency_p50_s", "latency_p95_s", "cost_per_query_usd", "mean_tool_calls",
]  # fmt: skip
SYSTEM_ORDER = [
    "llm_only",
    "rag",
    "whybot",
    "whybot_no_rerank",
    "whybot_no_verifier",
    "whybot_bm25_only",
    "whybot_dense_only",
]


def read(name: str) -> Any:
    path = RESULTS / name
    return json.loads(path.read_text()) if path.exists() else None


def split_block(name: str) -> dict[str, Any] | None:
    data = read(f"{name}/metrics.json")
    if data is None:
        return None
    systems = []
    for system in SYSTEM_ORDER:
        if system in data["systems"]:
            entry = data["systems"][system]
            complete = entry["metrics"]["errors"] == 0  # an interrupted run shows as "not run yet"
            systems.append({"system": system, "label": entry["label"], "group": entry["group"], "complete": complete,
                            "metrics": {k: entry["metrics"].get(k) if complete else None for k in TABLE_METRICS},
                            "extra": {k: v for k, v in entry["metrics"].items() if k not in TABLE_METRICS}})  # fmt: skip
    return {"run_date": data["run_date"], "n": data["n"], "systems": systems}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    dev = read("dev/metrics.json")
    kinds = manifest["kinds"]
    summary = {
        "generated_at": str(date.today()),
        "benchmark": {
            "version": manifest["version"],
            "seed": manifest["seed"],
            "scenarios": manifest["scenarios"],
            "dev": manifest["dev"],
            "test": manifest["test"],
            "decoys": kinds["decoy_loud"] + kinds["decoy_seasonal"],
            "unanswerable": kinds["unanswerable"],
            "injection": kinds["injection"],
            "cause_types": len(manifest["cause_types"]),
            "documents": manifest["documents"],
            "metric_rows": manifest["metric_rows"],
        },  # fmt: skip
        "models": {
            "agent": dev["agent_model"] if dev else None,
            "judge": dev["judge_model"] if dev else None,
        },
        "splits": {"dev": split_block("dev"), "test": split_block("test")},
        "retrieval": read("retrieval_dev.json"),
        "judge_calibration": read("judge_calibration.json"),
        "security": read("security.json"),
        "error_analysis": read("error_analysis.json"),
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {RESULTS / 'summary.json'}")


if __name__ == "__main__":
    main()
