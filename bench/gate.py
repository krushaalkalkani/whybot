"""CI eval gate. Fails the build if quality drops on the 20-scenario smoke subset.

Compares a fresh metrics.json (WhyBot on dev smoke) with the committed baseline in
bench/gate_baseline.json. The build fails when accuracy@1 or citation precision is
lower than the baseline by more than the margin.

  python -m bench.gate results/dev_smoke/metrics.json
  python -m bench.gate results/dev_smoke/metrics.json --update   (after a deliberate change)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASELINE = Path(__file__).parent / "gate_baseline.json"
GATED = ["accuracy_at_1", "citation_precision"]
MARGIN = 0.05  # 5 points. On 20 scenarios one scenario is 5 points of accuracy.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics_file")
    parser.add_argument("--update", action="store_true", help="write the current numbers as the new baseline")
    args = parser.parse_args()
    current = json.loads(Path(args.metrics_file).read_text())["systems"]["whybot"]["metrics"]
    if args.update:
        BASELINE.write_text(json.dumps({"margin": MARGIN, **{k: current[k] for k in GATED}}, indent=2) + "\n")
        print(f"baseline updated: {BASELINE.read_text()}")
        return
    baseline = json.loads(BASELINE.read_text())
    failed = False
    for key in GATED:
        drop = baseline[key] - (current[key] or 0.0)
        status = "FAIL" if drop > baseline["margin"] else "ok"
        failed = failed or status == "FAIL"
        print(
            f"{status:4s} {key}: baseline {baseline[key]:.3f}, now {current[key]}, allowed drop {baseline['margin']}"
        )
    if current["errors"]:
        print(f"FAIL {current['errors']} scenarios crashed")
        failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
