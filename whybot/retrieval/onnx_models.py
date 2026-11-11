"""The two small neural models used by retrieval, run locally on CPU with ONNX Runtime.

- Embedder: bge-small-en-v1.5 turns a text into a 384-number vector. Texts with a
  similar meaning get vectors that point the same way.
- Reranker: ms-marco-MiniLM-L-6-v2 is a cross-encoder. It reads the query and one
  passage together and gives a relevance score. Slower, but more accurate.

Both are the quantized (int8) ONNX exports, about 34 MB and 23 MB. No PyTorch needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

EMBED_REPO = "Xenova/bge-small-en-v1.5"
RERANK_REPO = "Xenova/ms-marco-MiniLM-L-6-v2"
ONNX_FILE = "onnx/model_quantized.onnx"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge convention
EMBED_DIM = 384


def _load(repo: str, models_dir: Path, max_length: int) -> tuple[ort.InferenceSession, Tokenizer]:
    """Download the model once into models_dir, then load it."""
    local = models_dir / repo.split("/")[1]
    for name in (ONNX_FILE, "tokenizer.json"):
        if not (local / name).exists():
            hf_hub_download(repo, name, local_dir=local)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(str(local / ONNX_FILE), options, providers=["CPUExecutionProvider"])
    tokenizer = Tokenizer.from_file(str(local / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=max_length)
    tokenizer.enable_padding()
    return session, tokenizer


def _inputs(session: ort.InferenceSession, encodings: list) -> dict[str, np.ndarray]:
    wanted = {i.name for i in session.get_inputs()}
    feeds = {
        "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
    }
    return {k: v for k, v in feeds.items() if k in wanted}


class Embedder:
    def __init__(self, models_dir: Path) -> None:
        self.session, self.tokenizer = _load(EMBED_REPO, models_dir, max_length=256)

    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Return one unit-length vector per text."""
        out = []
        for i in range(0, len(texts), batch_size):
            encodings = self.tokenizer.encode_batch(texts[i : i + batch_size])
            hidden = self.session.run(None, _inputs(self.session, encodings))[0]
            cls = hidden[:, 0, :]  # bge uses the first ([CLS]) token as the sentence vector
            out.append(cls / np.linalg.norm(cls, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32)

    def embed_query(self, query: str) -> list[float]:
        return [float(x) for x in self.embed([QUERY_PREFIX + query])[0]]


class Reranker:
    def __init__(self, models_dir: Path) -> None:
        self.session, self.tokenizer = _load(RERANK_REPO, models_dir, max_length=384)

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Higher score = the passage answers the query better."""
        if not passages:
            return []
        encodings = self.tokenizer.encode_batch([(query, p) for p in passages])
        logits = self.session.run(None, _inputs(self.session, encodings))[0]
        return [float(x) for x in logits.reshape(-1)]
