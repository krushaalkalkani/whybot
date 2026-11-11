"""Load the benchmark files into Postgres: metrics, documents, chunks with embeddings.

Run:  python -m bench.load            (uses DATABASE_URL)
      python -m bench.load --embed    (recompute bench/data/v1/embeddings.npy first)

Embeddings are stored in the repo as a float16 .npy file so loading is fast and gives
the same vectors on every machine. `--embed` rebuilds that file with the ONNX model.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
from psycopg import sql

from whybot.config import get_settings
from whybot.db import Conn, apply_schema, connect, vector_literal
from whybot.retrieval.search import chunk_text

DATA_DIR = Path(__file__).parent / "data" / "v1"


def read_documents() -> list[dict]:
    return [json.loads(line) for line in open(DATA_DIR / "documents.jsonl")]


def read_scenarios(split: str | None = None, smoke: bool = False) -> list[dict]:
    rows = [json.loads(line) for line in open(DATA_DIR / "scenarios.jsonl")]
    if split:
        rows = [r for r in rows if r["split"] == split]
    if smoke:
        rows = [r for r in rows if r["smoke"]]
    return rows


def all_chunks(documents: list[dict]) -> list[tuple[str, int, str]]:
    """(doc id, chunk number, text) for every passage, in a fixed order."""
    out = []
    for doc in documents:
        for idx, text in enumerate(chunk_text(doc["title"], doc["body"])):
            out.append((doc["id"], idx, text))
    return out


def compute_embeddings(chunks: list[tuple[str, int, str]]) -> np.ndarray:
    from whybot.retrieval.onnx_models import Embedder

    embedder = Embedder(get_settings().models_dir)
    return embedder.embed([text for _, _, text in chunks]).astype(np.float16)


def ensure_readonly_role(conn: Conn, readonly_url: str) -> None:
    """Create the SELECT-only role named in DATABASE_URL_READONLY (user and password come from that URL)."""
    parsed = urlparse(readonly_url)
    if not parsed.username or not parsed.password:
        return
    role, password = sql.Identifier(parsed.username), sql.Literal(unquote(parsed.password))
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (parsed.username,)).fetchone()
    verb = sql.SQL("ALTER") if exists else sql.SQL("CREATE")
    conn.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(verb, role, password))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT SELECT ON daily_metrics TO {}").format(role))


def load(conn: Conn, embeddings: np.ndarray) -> dict[str, int]:
    apply_schema(conn)
    documents = read_documents()
    chunks = all_chunks(documents)
    assert len(chunks) == len(embeddings), "embeddings.npy does not match documents.jsonl; run with --embed"

    with conn.transaction():
        conn.execute("TRUNCATE daily_metrics, chunks, documents CASCADE")
        with conn.cursor().copy(
            "COPY daily_metrics (date, region, platform, channel, sessions, checkout_starts, payment_attempts, payment_failures, orders, revenue) FROM STDIN"
        ) as copy:
            rows = csv.reader(open(DATA_DIR / "metrics.csv"))
            next(rows)
            n_metrics = 0
            for row in rows:
                copy.write_row(row)
                n_metrics += 1
        with conn.cursor().copy(
            "COPY documents (id, source, created_at, title, body, meta) FROM STDIN"
        ) as copy:
            for doc in documents:
                copy.write_row(
                    (
                        doc["id"],
                        doc["source"],
                        doc["created_at"],
                        doc["title"],
                        doc["body"],
                        json.dumps(doc["meta"]),
                    )
                )
        with conn.cursor().copy("COPY chunks (doc_id, idx, text, embedding) FROM STDIN") as copy:
            for (doc_id, idx, text), vector in zip(chunks, embeddings, strict=True):
                copy.write_row((doc_id, idx, text, vector_literal([float(x) for x in vector])))
    return {"metric_rows": n_metrics, "documents": len(documents), "chunks": len(chunks)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed", action="store_true", help="recompute embeddings.npy with the ONNX model")
    parser.add_argument("--if-empty", action="store_true", help="skip if the database already has data")
    args = parser.parse_args()
    settings = get_settings()
    path = DATA_DIR / "embeddings.npy"
    if args.embed or not path.exists():
        started = time.time()
        np.save(path, compute_embeddings(all_chunks(read_documents())))
        print(f"embedded in {time.time() - started:.0f}s -> {path}")
    conn = connect(settings.database_url)
    apply_schema(conn)
    if args.if_empty and conn.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
        print("database already loaded; skipping")
    else:
        print(load(conn, np.load(path)))
    if settings.database_url_readonly != settings.database_url:
        ensure_readonly_role(conn, settings.database_url_readonly)
        print("read-only role ready")


if __name__ == "__main__":
    main()
