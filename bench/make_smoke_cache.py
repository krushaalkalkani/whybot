"""Build the small LLM cache that the CI eval gate replays.

Replays WhyBot on the 20-scenario smoke subset from the full local cache, then writes
only the LLM entries it used, plus the document IDs every search returned, to
bench/cache/smoke/. CI replays both, so the gate does not depend on tiny numeric
differences between machines in the ONNX models. Run after a dev eval:

  python -m bench.make_smoke_cache
"""

from __future__ import annotations

import json

from bench.load import read_scenarios
from bench.run_eval import Workers, run_one
from whybot.config import REPO_ROOT
from whybot.llm import ClaudeLLM


def main() -> None:
    workers = Workers()
    llm = ClaudeLLM(cache_dir=REPO_ROOT / "bench" / "cache" / "live", replay_only=True)
    for scenario in read_scenarios("dev", smoke=True):
        record = run_one("whybot", scenario, workers, llm, use_judge=False)
        assert "error" not in record, record.get("error")
    out = REPO_ROOT / "bench" / "cache" / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "llm_cache.jsonl", "w") as f:
        for key in sorted(llm.used_keys):
            f.write(json.dumps({"key": key, "result": llm._cache[key]}, sort_keys=True) + "\n")
    searches = dict(sorted(workers.shared.recorded.items()))
    (out / "search_cache.json").write_text(json.dumps(searches, indent=0) + "\n")
    print(f"wrote {len(llm.used_keys)} LLM entries and {len(searches)} searches to {out}")


if __name__ == "__main__":
    main()
