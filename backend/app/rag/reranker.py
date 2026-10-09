"""
Cross-encoder reranker for hybrid search candidates.

Wraps BAAI/bge-reranker-v2-m3 with lazy loading and graceful fallback.
Controlled by settings.RERANK_ENABLED and settings.RERANK_CANDIDATES.
Runs ONLY on results that have already passed access filtering.
"""

from __future__ import annotations

import logging
import os
from typing import Any

# CRITICAL: Disable tokenizer thread parallelism to prevent Rayon/OpenMP deadlocks on Windows
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from app.config import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Singleton CrossEncoder reranker."""

    _instance: Reranker | None = None
    _model = None
    _failed: bool = False

    def __new__(cls) -> Reranker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self) -> None:
        """Load CrossEncoder model once. Failures trigger graceful fallback."""
        if self._model is None and not self._failed:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(settings.RERANK_MODEL, device="cpu")
                logger.info("Loaded reranker model: %s", settings.RERANK_MODEL)
            except Exception as exc:
                self._failed = True
                logger.warning(
                    "Failed to load reranker model %s: %s. Falling back to fused order.",
                    settings.RERANK_MODEL,
                    exc,
                )

    def score_pairs(self, pairs: list[list[str]]) -> list[float]:
        """Score (query, text) pairs directly with CrossEncoder."""
        if not pairs:
            return []
        self._load()
        if self._model is None:
            return [1.0] * len(pairs)
        try:
            scores = self._model.predict(pairs)
            return [float(s) for s in scores]
        except Exception as exc:
            logger.warning("Reranker score_pairs failed: %s", exc)
            return [1.0] * len(pairs)

    def rerank(self, query: str, results: list[Any], top_k: int) -> list[Any]:
        """
        Rerank already-filtered search results.
        If reranking model is missing or inference fails, logs a warning and
        falls back to fused order without crashing.
        """
        if not results:
            return []

        self._load()
        if self._model is None:
            return results[:top_k]

        try:
            candidates = results[: settings.RERANK_CANDIDATES]
            pairs = [
                [query, getattr(c, "text", "") if hasattr(c, "text") else c.get("text", "")]
                for c in candidates
            ]
            scores = self._model.predict(pairs)

            scored = []
            for item, score in zip(candidates, scores):
                # Update score attribute if present
                if hasattr(item, "score"):
                    item.score = float(score)
                elif isinstance(item, dict):
                    item["score"] = float(score)
                scored.append(item)

            scored.sort(
                key=lambda x: getattr(x, "score", 0.0) if hasattr(x, "score") else x.get("score", 0.0),
                reverse=True,
            )
            return scored[:top_k]
        except Exception as exc:
            logger.warning("Reranking inference failed: %s. Falling back to fused order.", exc)
            return results[:top_k]
