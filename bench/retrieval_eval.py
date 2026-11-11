"""Retrieval-only check: does search find the documents that name the cause?

For every dev scenario with key documents, search with the raw question in a window of
2 days around the question date, and look at the top 10. No LLM is involved.

  recall@10  share of key documents found in the top 10 (averaged over scenarios)
  MRR        mean of 1 / rank of the first key document (0 if none is found)

Run:  python -m bench.retrieval_eval      -> results/retrieval_dev.json
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from bench.load import read_scenarios
from whybot.config import REPO_ROOT, RetrievalConfig, get_settings
from whybot.db import connect
from whybot.retrieval.search import Retriever

CONFIGS = {
    "BM25 only": RetrievalConfig(use_dense=False, use_rerank=False),
    "Dense only": RetrievalConfig(use_bm25=False, use_rerank=False),
    "Hybrid (RRF)": RetrievalConfig(use_rerank=False),
    "Hybrid + reranker": RetrievalConfig(),
}


def main() -> None:
    settings = get_settings()
    retriever = Retriever(connect(settings.database_url), settings.models_dir)
    scenarios = [s for s in read_scenarios("dev") if s["key_evidence_ids"]]
    rows = []
    for name, config in CONFIGS.items():
        recalls, reciprocal_ranks = [], []
        for s in scenarios:
            day = date.fromisoformat(s["date"])
            cards = retriever.search(
                s["question"], config, day - timedelta(days=2), day + timedelta(days=2), k=10
            )
            ids = [c.id for c in cards]
            key = set(s["key_evidence_ids"])
            recalls.append(len(key & set(ids)) / len(key))
            first = next((rank for rank, doc_id in enumerate(ids, start=1) if doc_id in key), None)
            reciprocal_ranks.append(1.0 / first if first else 0.0)
        rows.append(
            {
                "config": name,
                "recall_at_10": round(sum(recalls) / len(recalls), 4),
                "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
            }
        )
        print(rows[-1])
    out = {"split": "dev", "n_queries": len(scenarios), "window_days": 2, "rows": rows}
    (REPO_ROOT / "results" / "retrieval_dev.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
