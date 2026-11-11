"""Judge calibration: does the LLM judge agree with a human?

  python -m bench.calibrate export           pick 30 judged claims from the dev runs and build
                                             results/calibration/label.html (open it in a browser)
  python -m bench.calibrate score FILE.csv   compare your labels with the judge
                                             -> results/judge_calibration.json

The page shows a claim and the evidence it cites. You click "Supported" or "Not supported".
The judge's own verdict is not shown, so it cannot bias you. Half of the sample are claims
the judge accepted and half are claims it rejected (as far as the runs allow).
"""

from __future__ import annotations

import csv
import html
import json
import random
import sys
from typing import Any

from bench.judge import claim_items
from whybot.config import REPO_ROOT, get_settings
from whybot.schemas import Report

OUT = REPO_ROOT / "results" / "calibration"
SOURCES = ["rag", "whybot", "whybot_no_verifier", "whybot_bm25_only"]
N_ITEMS = 30
SEED = 11


def export() -> None:
    pool: list[dict[str, Any]] = []
    for system in SOURCES:
        path = REPO_ROOT / "results" / "dev" / f"{system}.jsonl"
        if not path.exists():
            continue
        for line in open(path):
            record = json.loads(line)
            if not record.get("judge") or not record.get("report"):
                continue
            items = claim_items(Report.model_validate(record["report"]))
            for item, verdict in zip(items, record["judge"]["verdicts"], strict=True):
                if item["evidence"]:  # claims with no evidence never reached the judge
                    pool.append(
                        {
                            **item,
                            "judge_faithful": verdict,
                            "system": system,
                            "scenario_id": record["scenario_id"],
                        }
                    )
    rng = random.Random(SEED)
    rng.shuffle(pool)
    seen: set[str] = set()
    unique = [p for p in pool if not (p["claim"] in seen or seen.add(p["claim"]))]  # type: ignore[func-returns-value]
    rejected = [p for p in unique if not p["judge_faithful"]][: N_ITEMS // 2]
    accepted = [p for p in unique if p["judge_faithful"]][: N_ITEMS - len(rejected)]
    sample = rejected + accepted
    rng.shuffle(sample)
    for i, item in enumerate(sample, start=1):
        item["item_id"] = i
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.json").write_text(json.dumps(sample, indent=1) + "\n")

    cards = []
    for item in sample:
        evidence = "".join(
            f"<div class='ev'><b>{html.escape(e['id'])}</b> - {html.escape(e['source'])} - {html.escape(e['date'])} - "
            f"{html.escape(e['title'])}<pre>{html.escape(e['body'])}</pre></div>"
            for e in item["evidence"]
        )
        cards.append(
            f"<section data-id='{item['item_id']}'><h3>Claim {item['item_id']} of {len(sample)}</h3>"
            f"<p class='claim'>{html.escape(item['claim'])}</p>{evidence}"
            "<button data-v='1'>Supported</button> <button data-v='0'>Not supported</button> <span class='picked'></span></section>"
        )
    page = f"""<!doctype html><meta charset="utf-8"><title>WhyBot judge calibration</title>
<style>body{{font:16px system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}}section{{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}}
.claim{{font-size:1.1rem;font-weight:600}}.ev{{background:#f4f4f4;padding:.5rem;margin:.5rem 0;border-radius:6px}}pre{{white-space:pre-wrap;margin:.3rem 0 0}}
button{{font:inherit;padding:.4rem 1rem;cursor:pointer}}.done{{border-color:#2a7}}#bar{{position:sticky;top:0;background:#fff;padding:.5rem 0;border-bottom:1px solid #ccc}}</style>
<div id="bar"><b>Judge calibration.</b> For each claim: does the evidence shown support it? Supported = the evidence states it or
directly shows it. If the claim says more than the evidence, pick Not supported. <span id="count">0</span>/{len(sample)} done.
<button id="save" disabled>Download labels.csv</button></div>
{"".join(cards)}
<script>
const labels = {{}};
document.querySelectorAll('section button').forEach(b => b.onclick = () => {{
  const s = b.closest('section'); labels[s.dataset.id] = b.dataset.v; s.classList.add('done');
  s.querySelector('.picked').textContent = b.dataset.v === '1' ? 'You chose: Supported' : 'You chose: Not supported';
  const n = Object.keys(labels).length; document.getElementById('count').textContent = n;
  document.getElementById('save').disabled = n < {len(sample)};
}});
document.getElementById('save').onclick = () => {{
  const csv = 'item_id,human_supported\\n' + Object.entries(labels).map(([k, v]) => k + ',' + v).join('\\n') + '\\n';
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {{type: 'text/csv'}}));
  a.download = 'labels.csv'; a.click();
}};
</script>"""
    (OUT / "label.html").write_text(page)
    print(
        f"{len(sample)} items ({len(rejected)} judge-rejected, {len(accepted)} judge-accepted) -> {OUT / 'label.html'}"
    )


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    """Agreement corrected for chance. 1 = perfect, 0 = no better than chance."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    p_yes = (sum(a) / n) * (sum(b) / n)
    p_no = (1 - sum(a) / n) * (1 - sum(b) / n)
    expected = p_yes + p_no
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def score(labels_file: str) -> None:
    items = {item["item_id"]: item for item in json.loads((OUT / "items.json").read_text())}
    human = {
        int(row["item_id"]): row["human_supported"].strip() == "1"
        for row in csv.DictReader(open(labels_file))
    }
    ids = sorted(set(items) & set(human))
    judge = [bool(items[i]["judge_faithful"]) for i in ids]
    mine = [human[i] for i in ids]
    result = {
        "n": len(ids),
        "agreement": round(sum(j == h for j, h in zip(judge, mine, strict=True)) / len(ids), 4),
        "cohens_kappa": round(cohens_kappa(judge, mine), 4),
        "judge_model": get_settings().judge_model,
        "judge_said_supported": sum(judge),
        "human_said_supported": sum(mine),
        "disagreements": [i for i, j, h in zip(ids, judge, mine, strict=True) if j != h],
    }
    (OUT / "labels.csv").write_text(open(labels_file).read())
    (REPO_ROOT / "results" / "judge_calibration.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export()
    elif len(sys.argv) == 3 and sys.argv[1] == "score":
        score(sys.argv[2])
    else:
        sys.exit(__doc__)
