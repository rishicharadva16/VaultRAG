"""
Dense and sparse embedders.

Both are designed for dependency injection: tests can substitute fakes
that don't load bge-m3 or the BM25 model.
"""

from __future__ import annotations

import numpy as np
from app.config import settings


class DenseEmbedder:
    """Sentence-transformers dense embedder. Lazy-loaded singleton."""

    _instance: DenseEmbedder | None = None
    _model = None

    def __new__(cls) -> DenseEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                settings.EMBED_MODEL, device="cpu",
            )

    @property
    def dense_size(self) -> int:
        self._load()
        if hasattr(self._model, "get_embedding_dimension"):
            return self._model.get_embedding_dimension()
        return self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns normalized vectors."""
        self._load()
        vecs = self._model.encode(
            texts, batch_size=16, normalize_embeddings=True,
        )
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return self.embed([text])[0]


class SparseEmbedder:
    """Fastembed BM25 sparse embedder."""

    _instance: SparseEmbedder | None = None
    _model = None

    def __new__(cls) -> SparseEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is None:
            from fastembed import SparseTextEmbedding
            self._model = SparseTextEmbedding(model_name=settings.SPARSE_MODEL)

    def embed_sparse(self, texts: list[str]) -> list[dict]:
        """Embed documents. Returns list of {"indices": [...], "values": [...]}."""
        self._load()
        results = []
        for emb in self._model.embed(texts):
            results.append({
                "indices": emb.indices.tolist(),
                "values": emb.values.tolist(),
            })
        return results

    def embed_sparse_query(self, text: str) -> dict:
        """Embed a single query (uses query_embed if available)."""
        self._load()
        emb = next(self._model.query_embed(text))
        return {"indices": emb.indices.tolist(), "values": emb.values.tolist()}


# ── Fake embedders for tests (no ML models needed) ───────────

class FakeDenseEmbedder:
    """Deterministic dense embedder for tests. No real model loaded."""

    def __init__(self, size: int = 8):
        self._size = size

    @property
    def dense_size(self) -> int:
        return self._size

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = []
        for t in texts:
            rng = np.random.RandomState(hash(t) % 2**31)
            v = rng.randn(self._size).astype(np.float32)
            v = v / (np.linalg.norm(v) + 1e-9)
            vecs.append(v.tolist())
        return vecs

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class FakeSparseEmbedder:
    """Deterministic sparse embedder for tests. No real model loaded."""

    def embed_sparse(self, texts: list[str]) -> list[dict]:
        results = []
        for t in texts:
            rng = np.random.RandomState(hash(t) % 2**31)
            n = max(3, len(t.split()) // 2)
            indices = sorted(rng.choice(10000, size=n, replace=False).tolist())
            values = rng.rand(n).tolist()
            results.append({"indices": indices, "values": values})
        return results

    def embed_sparse_query(self, text: str) -> dict:
        return self.embed_sparse([text])[0]
