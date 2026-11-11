"""Hybrid retrieval: BM25 + dense vectors -> reciprocal rank fusion -> cross-encoder rerank.

Pipeline for one query:
  1. BM25 keyword search over the passages (in memory).
  2. Dense search: embed the query, ask pgvector for the nearest passage vectors.
  3. Fuse the two ranked lists with reciprocal rank fusion (RRF).
  4. Rerank the best fused candidates with a cross-encoder.
  5. Keep the best passage per document and return the top k documents.

Each stage has a switch in RetrievalConfig so the eval can measure what it adds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from whybot.config import RetrievalConfig
from whybot.db import Conn, vector_literal
from whybot.retrieval.bm25 import BM25Index
from whybot.retrieval.onnx_models import Embedder, Reranker
from whybot.schemas import EvidenceCard

RRF_K = 60  # standard constant: makes rank 1 vs rank 2 matter less than raw scores would


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Merge ranked lists. An item scores 1/(k + rank) in each list it appears in.

    RRF only uses ranks, so it does not care that BM25 scores and cosine
    similarities live on different scales.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def chunk_text(title: str, body: str, max_words: int = 120, overlap: int = 20) -> list[str]:
    """Split a document into passages of about 120 words. The title is repeated in each."""
    words = body.split()
    if len(words) <= max_words:
        return [f"{title}\n{body}"]
    chunks = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        chunks.append(f"{title}\n{' '.join(words[start : start + max_words])}")
        if start + max_words >= len(words):
            break
    return chunks


@dataclass
class ChunkRow:
    id: int
    doc_id: str
    text: str
    source: str
    created_at: date


class Retriever:
    def __init__(self, conn: Conn, models_dir: Path) -> None:
        self.conn = conn
        self.models_dir = models_dir
        self.chunks: dict[int, ChunkRow] = {}
        self.bm25: BM25Index | None = None
        self._embedder: Embedder | None = None
        self._reranker: Reranker | None = None
        # Search replay, used by the CI eval gate. ONNX scores differ in the last bits between
        # machines, which can reorder near-ties. Replaying recorded result IDs keeps the gate stable.
        self.recorded: dict[str, list[str]] = {}  # search key -> document IDs returned
        self.replay: dict[str, list[str]] | None = None  # if set, known searches return these IDs

    def share(self, conn: Conn) -> Retriever:
        """A copy bound to another connection that reuses the loaded index and models.
        Used to give each request or thread its own database connection."""
        self.load_index()
        other = Retriever(conn, self.models_dir)
        other.chunks, other.bm25 = self.chunks, self.bm25
        other.recorded, other.replay = self.recorded, self.replay
        if self.replay is None:  # replays do not need the models
            other._embedder, other._reranker = self.embedder, self.reranker
        return other

    # The models and the BM25 index are loaded on first use, so a cold start only pays for what it needs.
    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder(self.models_dir)
        return self._embedder

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = Reranker(self.models_dir)
        return self._reranker

    def load_index(self) -> None:
        if self.bm25 is not None:
            return
        rows = self.conn.execute(
            "SELECT c.id, c.doc_id, c.text, d.source, d.created_at FROM chunks c JOIN documents d ON d.id = c.doc_id"
        ).fetchall()
        self.chunks = {
            r["id"]: ChunkRow(r["id"], r["doc_id"], r["text"], r["source"], r["created_at"]) for r in rows
        }
        self.bm25 = BM25Index({c.id: c.text for c in self.chunks.values()})

    def _allowed(self, date_from: date | None, date_to: date | None, source: str | None) -> set[int] | None:
        if date_from is None and date_to is None and source is None:
            return None
        return {
            c.id
            for c in self.chunks.values()
            if (date_from is None or c.created_at >= date_from)
            and (date_to is None or c.created_at <= date_to)
            and (source is None or c.source == source)
        }

    def _dense(
        self, query: str, date_from: date | None, date_to: date | None, source: str | None, k: int
    ) -> list[int]:
        """Nearest passages by cosine distance (the <=> operator), filtered in SQL."""
        vector = vector_literal(self.embedder.embed_query(query))
        rows = self.conn.execute(
            """
            SELECT c.id FROM chunks c JOIN documents d ON d.id = c.doc_id
            WHERE (%(date_from)s::date IS NULL OR d.created_at >= %(date_from)s::date)
              AND (%(date_to)s::date IS NULL OR d.created_at <= %(date_to)s::date)
              AND (%(source)s::text IS NULL OR d.source = %(source)s::text)
            ORDER BY c.embedding <=> %(vector)s::vector, c.id
            LIMIT %(k)s
            """,
            {"date_from": date_from, "date_to": date_to, "source": source, "vector": vector, "k": k},
        ).fetchall()
        return [r["id"] for r in rows]

    def search(
        self,
        query: str,
        config: RetrievalConfig,
        date_from: date | None = None,
        date_to: date | None = None,
        source: str | None = None,
        k: int = 8,
    ) -> list[EvidenceCard]:
        key = f"{query}|{config}|{date_from}|{date_to}|{source}|{k}"
        if self.replay is not None and key in self.replay:
            return self.fetch_cards(self.replay[key])
        self.load_index()
        assert self.bm25 is not None
        rankings: list[list[int]] = []
        if config.use_bm25:
            allowed = self._allowed(date_from, date_to, source)
            rankings.append([cid for cid, _ in self.bm25.search(query, allowed, config.candidates)])
        if config.use_dense:
            rankings.append(self._dense(query, date_from, date_to, source, config.candidates))
        fused = reciprocal_rank_fusion(rankings)

        if config.use_rerank:
            top = [cid for cid, _ in fused[: config.rerank_top]]
            scores = self.reranker.score(query, [self.chunks[cid].text for cid in top])
            fused = sorted(zip(top, scores, strict=True), key=lambda pair: (-pair[1], pair[0]))

        best_per_doc: dict[str, float] = {}
        for chunk_id, score in fused:  # already sorted, so the first hit per document is its best
            best_per_doc.setdefault(self.chunks[chunk_id].doc_id, score)
        doc_ids = list(best_per_doc)[:k]
        self.recorded[key] = doc_ids
        return self.fetch_cards(doc_ids, best_per_doc)

    def fetch_cards(self, doc_ids: list[str], scores: dict[str, float] | None = None) -> list[EvidenceCard]:
        if not doc_ids:
            return []
        rows = self.conn.execute(
            "SELECT id, source, created_at, title, body, meta FROM documents WHERE id = ANY(%s)", (doc_ids,)
        ).fetchall()
        by_id = {r["id"]: r for r in rows}
        cards = []
        for doc_id in doc_ids:
            if doc_id not in by_id:
                continue
            r = by_id[doc_id]
            cards.append(
                EvidenceCard(
                    id=doc_id,
                    source=r["source"],
                    title=r["title"],
                    date=str(r["created_at"]),
                    body=r["body"],
                    meta=r["meta"],
                    score=round(scores[doc_id], 4) if scores else None,
                )
            )
        return cards
