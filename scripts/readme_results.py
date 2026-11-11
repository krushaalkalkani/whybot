"""Rewrite the results blocks in README.md and docs/RESUME.md from results/summary.json.

Run:  python scripts/readme_results.py     (after python -m bench.summarize)
No number in those files is typed by hand. A value that has not been run prints "not run yet".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
NOT_RUN = "not run yet"


def pct(value: Any) -> str:
    return NOT_RUN if value is None else f"{value * 100:.1f}%"


def num(value: Any, digits: int, unit: str = "") -> str:
    return NOT_RUN if value is None else f"{value:.{digits}f}{unit}"


def usd(value: Any) -> str:
    return NOT_RUN if value is None else f"${value:.4f}"


def system_table(split: dict[str, Any] | None, group: str | None) -> list[str]:
    if split is None:
        return [NOT_RUN.capitalize() + "."]
    lines = [
        "| System | Acc@1 | Acc@3 | Cite P | Cite R | Faithful | Abstain acc | Injection | p50 | p95 | USD/query | Tools |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in split["systems"]:
        if group and s["group"] != group and s["system"] != "whybot":
            continue
        m = s["metrics"]
        lines.append(
            f"| {s['label']} | {pct(m['accuracy_at_1'])} | {pct(m['accuracy_at_3'])} | {pct(m['citation_precision'])} | "
            f"{pct(m['citation_recall'])} | {pct(m['faithfulness'])} | {pct(m['abstention_accuracy'])} | "
            f"{pct(m['injection_resistance'])} | {num(m['latency_p50_s'], 1, 's')} | {num(m['latency_p95_s'], 1, 's')} | "
            f"{usd(m['cost_per_query_usd'])} | {num(m['mean_tool_calls'], 1)} |"
        )
    return lines


def readme_block(s: dict[str, Any]) -> str:
    b = s["benchmark"]
    lines = [
        f"Benchmark {b['version']} (seed {b['seed']}): {b['scenarios']} scenarios, {b['dev']} dev and {b['test']} test, "
        f"with {b['decoys']} decoys, {b['unanswerable']} unanswerable and {b['injection']} prompt-injection scenarios. "
        f"Agent model: `{s['models']['agent'] or NOT_RUN}`. Judge model: `{s['models']['judge'] or NOT_RUN}`.",
        "",
    ]
    for name, title in (("test", "Test split (frozen, run once)"), ("dev", "Dev split (used while building)")):
        split = s["splits"][name]
        when = f" Run {split['run_date']}, n = {split['n']}." if split else ""
        lines += [f"### {title}", "", f"Source: `results/{name}/metrics.json`.{when}", "", *system_table(split, "main"), ""]
        lines += [f"Ablations of WhyBot on the {name} split:", "", *system_table(split, "ablation"), ""]
    lines += ["### Retrieval only (dev, no LLM)", ""]
    r = s["retrieval"]
    if r:
        lines += [
            f"Source: `results/retrieval_dev.json`. Query = the raw question, documents within {r['window_days']} days, {r['n_queries']} scenarios.",
            "",
            "| Retrieval setup | Recall@10 of key documents | MRR |",
            "| --- | ---: | ---: |",
            *[f"| {row['config']} | {pct(row['recall_at_10'])} | {row['mrr']:.3f} |" for row in r["rows"]],
        ]
    else:
        lines.append(NOT_RUN.capitalize() + ".")
    lines += ["", "### Judge calibration", ""]
    c = s["judge_calibration"]
    if c:
        lines.append(
            f"Source: `results/judge_calibration.json`. {c['n']} hand-labelled claims. Judge agrees with the human on "
            f"**{pct(c['agreement'])}** (Cohen's kappa {c['cohens_kappa']:.2f}). Judge: `{c['judge_model']}`."
        )
    else:
        lines.append(NOT_RUN.capitalize() + ". Needs 30 hand labels (`python -m bench.calibrate export`).")
    lines += ["", "### Security tests", ""]
    sec = s["security"]
    if sec:
        groups: dict[str, list[bool]] = {}
        for t in sec["tests"]:
            groups.setdefault(t["owasp"], []).append(t["passed"])
        lines += [f"Source: `results/security.json` (pytest). {sec['passed']} of {sec['total']} test cases pass.", "", "| OWASP LLM Top 10 item | Test cases | Passed |", "| --- | ---: | ---: |"]
        lines += [f"| {name} | {len(v)} | {sum(v)} |" for name, v in sorted(groups.items())]
    else:
        lines.append(NOT_RUN.capitalize() + ".")
    lines += ["", "### Error analysis (test split)", ""]
    e = s["error_analysis"]
    if e:
        lines += ["| Failure category | Count | Example scenarios | What would fix it |", "| --- | ---: | --- | --- |"]
        lines += [f"| {row['category']} | {row['count']} | {', '.join(row['example_ids'])} | {row['fix']} |" for row in e]
    else:
        lines.append(NOT_RUN.capitalize() + ".")
    return "\n".join(lines)


def resume_block(s: dict[str, Any]) -> str:
    test = s["splits"]["test"]
    by_name = {x["system"]: x["metrics"] for x in test["systems"]} if test else {}
    w, rag, llm = by_name.get("whybot", {}), by_name.get("rag", {}), by_name.get("llm_only", {})
    b = s["benchmark"]
    sec = s["security"]
    c = s["judge_calibration"]
    return "\n".join(
        [
            f"1. Built WhyBot, a root-cause analysis agent (plain-Python state machine on the Claude API, no framework) with 4 typed tools "
            f"over Postgres + pgvector; reached **{pct(w.get('accuracy_at_1'))}** root-cause accuracy@1 on a held-out {b['test']}-scenario "
            f"test split vs **{pct(rag.get('accuracy_at_1'))}** for vector RAG and **{pct(llm.get('accuracy_at_1'))}** for LLM-only, "
            f"at **{usd(w.get('cost_per_query_usd'))}** per query (p50 latency **{num(w.get('latency_p50_s'), 1, ' s')}**).",
            "",
            f"2. Designed a seeded synthetic benchmark ({b['scenarios']} scenarios, {b['cause_types']} cause types, {b['decoys']} decoys, "
            f"{b['unanswerable']} unanswerable, {b['injection']} prompt-injection) and an eval harness with ablations and an LLM judge "
            f"(**{pct(c['agreement']) if c else NOT_RUN}** agreement with {c['n'] if c else 30} hand labels); a CI gate fails the build if "
            f"accuracy@1 or citation precision drops by more than 5 points.",
            "",
            f"3. Added hybrid retrieval (BM25 + ONNX bge-small + RRF + cross-encoder), a citation verifier and abstain rules: "
            f"**{pct(w.get('citation_precision'))}** citation precision, **{pct(w.get('abstention_accuracy'))}** abstention accuracy, "
            f"**{pct(w.get('injection_resistance'))}** prompt-injection resistance; "
            f"**{sec['passed'] if sec else NOT_RUN} of {sec['total'] if sec else NOT_RUN}** security test cases (OWASP LLM Top 10) pass.",
        ]
    )


def replace_block(path: Path, text: str) -> None:
    start, end = "<!-- results:start -->", "<!-- results:end -->"
    content = path.read_text()
    a, b = content.index(start), content.index(end)
    path.write_text(f"{content[: a + len(start)]}\n{text}\n{content[b:]}")


if __name__ == "__main__":
    summary = json.loads((ROOT / "results" / "summary.json").read_text())
    replace_block(ROOT / "README.md", readme_block(summary))
    replace_block(ROOT / "docs" / "RESUME.md", resume_block(summary))
    print("README.md and docs/RESUME.md updated from results/summary.json")
