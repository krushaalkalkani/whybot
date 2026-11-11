"""BM25 keyword search, written out in plain Python.

BM25 scores a passage higher when it contains the query's words, more so when the
word is rare in the whole collection (IDF) and when the passage is short.
It catches exact terms such as "checkout-service v4.12.0" that embeddings can blur.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

K1 = 1.5  # how fast repeated words stop adding score
B = 0.75  # how much long passages are penalised

STOPWORDS = frozenset(
    "a an and are as at be but by did do for from had has have how i if in is it its my of on or so "
    "that the their then there this to was we were what when which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase words and numbers. Keeps version-like tokens such as 'v4.12.0' whole."""
    tokens = re.findall(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*", text.lower())
    out = []
    for token in tokens:
        if token in STOPWORDS:
            continue
        out.append(token)
        if "-" in token or "." in token:  # also index the parts: "checkout-service" -> checkout, service
            out += [part for part in re.split(r"[.\-]", token) if part and part not in STOPWORDS]
    return out


class BM25Index:
    def __init__(self, passages: dict[int, str]) -> None:
        """passages maps a chunk id to its text."""
        self.doc_len: dict[int, int] = {}
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(chunk id, count)]
        for chunk_id, text in passages.items():
            counts = Counter(tokenize(text))
            self.doc_len[chunk_id] = sum(counts.values())
            for term, count in counts.items():
                self.postings[term].append((chunk_id, count))
        self.n = len(passages)
        self.avg_len = sum(self.doc_len.values()) / max(1, self.n)

    def idf(self, term: str) -> float:
        df = len(self.postings.get(term, ()))
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, allowed: set[int] | None = None, k: int = 30) -> list[tuple[int, float]]:
        """Return the top-k (chunk id, score). `allowed` limits the search, e.g. to a date range."""
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf(term)
            for chunk_id, count in self.postings.get(term, ()):
                if allowed is not None and chunk_id not in allowed:
                    continue
                norm = count + K1 * (1 - B + B * self.doc_len[chunk_id] / self.avg_len)
                scores[chunk_id] += idf * count * (K1 + 1) / norm
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:k]
