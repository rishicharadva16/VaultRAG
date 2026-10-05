"""
Secure vector store gateway.

RULE: This module is the ONLY code in the project allowed to import qdrant_client.
      All other modules must go through SecureStore to interact with Qdrant.
      This ensures every query passes through ACL filtering.

PAYLOAD DESIGN:
    Qdrant payloads accept lists natively, so acl_tokens is stored as a plain
    JSON array of permission strings (role:*, emp:*, dept:*, rolemp:*, usr:*).
"""

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import settings
from app.security.principals import Principal

# Payload index definitions: (field_name, schema_type)
_KEYWORD_FIELDS = ["acl_tokens", "doc_id", "source_doc", "source_type", "corpus", "owner_id"]
_INTEGER_FIELDS: list[str] = []
_BOOL_FIELDS = ["deleted"]


@dataclass
class SearchResult:
    chunk_id: str
    source_id: str
    file: str
    page: int | None
    corpus: str
    text: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "file": self.file,
            "page": self.page,
            "corpus": self.corpus,
            "text": self.text,
            "score": self.score,
        }


class SecureStore:
    """Single gateway to Qdrant. All access control is enforced here."""

    def __init__(self, url: str | None = None):
        self._client = QdrantClient(url=url or settings.QDRANT_URL)

    # ── Health ────────────────────────────────────────────────

    def health(self) -> dict:
        """Return {"status": "ok"} or {"status": "error", "detail": ...}."""
        try:
            self._client.get_collections()
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    # ── Collection management ─────────────────────────────────

    def drop_collection(self, collection: str | None = None) -> None:
        """Drop collection if it exists (safe / idempotent)."""
        name = collection or settings.QDRANT_COLLECTION
        try:
            existing = [c.name for c in self._client.get_collections().collections]
            if name in existing:
                self._client.delete_collection(name)
        except Exception as exc:
            # Re-check or ignore if already gone
            pass

    def delete_collection(self, collection: str) -> None:
        """Delete collection entirely (alias for drop_collection)."""
        self.drop_collection(collection)

    def ensure_collection(
        self, dense_size: int, collection: str | None = None,
    ) -> None:
        """
        Create the collection if it doesn't exist (idempotent).
        Named vectors: "dense" (cosine) and "sparse" (IDF modifier).
        Raises if an existing collection has a different dense vector size.
        """
        name = collection or settings.QDRANT_COLLECTION
        existing = [c.name for c in self._client.get_collections().collections]

        if name in existing:
            info = self._client.get_collection(name)
            # Check dense vector size matches
            vectors_config = info.config.params.vectors
            if isinstance(vectors_config, dict) and "dense" in vectors_config:
                existing_size = vectors_config["dense"].size
                if existing_size != dense_size:
                    raise RuntimeError(
                        f"Collection {name!r} exists with dense size {existing_size}, "
                        f"but requested {dense_size}"
                    )
        else:
            self._client.create_collection(
                collection_name=name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=dense_size, distance=models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    ),
                },
            )

        # Create payload indexes (idempotent – skip if already present)
        self._ensure_indexes(name)

    def _ensure_indexes(self, collection: str) -> None:
        """Create payload indexes, skipping any that already exist."""
        info = self._client.get_collection(collection)
        existing = set(info.payload_schema.keys()) if info.payload_schema else set()

        for field in _KEYWORD_FIELDS:
            if field not in existing:
                self._client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        for field in _INTEGER_FIELDS:
            if field not in existing:
                self._client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.INTEGER,
                )
        for field in _BOOL_FIELDS:
            if field not in existing:
                self._client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.BOOL,
                )

    # ── Upsert ────────────────────────────────────────────────

    def upsert_chunks(
        self,
        chunks: list,
        dense_vectors: list[list[float]],
        sparse_vectors: list,
        collection: str | None = None,
    ) -> None:
        """
        Upsert chunks with named dense and sparse vectors. Batches of 64.
        Re-running updates existing points (deterministic point ids).
        """
        name = collection or settings.QDRANT_COLLECTION
        from app.index.schema import point_id  # local import to avoid circular

        batch_size = 64
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_dense = dense_vectors[i:i + batch_size]
            batch_sparse = sparse_vectors[i:i + batch_size]

            points = []
            for chunk, dvec, svec in zip(batch_chunks, batch_dense, batch_sparse):
                pid = point_id(chunk.chunk_id)
                named_vectors = {
                    "dense": dvec,
                    "sparse": models.SparseVector(
                        indices=svec["indices"],
                        values=svec["values"],
                    ),
                }
                points.append(models.PointStruct(
                    id=pid,
                    vector=named_vectors,
                    payload=chunk.to_payload(),
                ))

            self._client.upsert(collection_name=name, points=points)

    # ── Delete ────────────────────────────────────────────────

    def delete_by_doc(self, doc_id: str, collection: str | None = None) -> None:
        """Remove all points for a given doc_id (used before re-ingesting)."""
        name = collection or settings.QDRANT_COLLECTION
        self._client.delete(
            collection_name=name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(
                        key="doc_id",
                        match=models.MatchValue(value=doc_id),
                    )]
                )
            ),
        )

    # ── Read helpers ──────────────────────────────────────────

    def admin_scroll(
        self, limit: int = 10, doc_id: str | None = None,
        collection: str | None = None,
    ) -> list:
        """
        Read helper for scripts and tests only. NOT for API use.
        Returns raw Qdrant points.
        """
        name = collection or settings.QDRANT_COLLECTION
        scroll_filter = None
        if doc_id:
            scroll_filter = models.Filter(
                must=[models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id),
                )]
            )
        points, _next = self._client.scroll(
            collection_name=name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return points

    def count(self, doc_id: str | None = None, collection: str | None = None) -> int:
        """Count points, optionally filtered by doc_id."""
        name = collection or settings.QDRANT_COLLECTION
        if doc_id:
            result = self._client.count(
                collection_name=name,
                count_filter=models.Filter(
                    must=[models.FieldCondition(
                        key="doc_id",
                        match=models.MatchValue(value=doc_id),
                    )]
                ),
                exact=True,
            )
        else:
            result = self._client.count(collection_name=name, exact=True)
        return result.count

    def get_collection_info(self, collection: str | None = None):
        """Return collection info (for tests checking payload indexes)."""
        name = collection or settings.QDRANT_COLLECTION
        return self._client.get_collection(name)

    # ── Search (Step 3) ───────────────────────────────────────

    def search(
        self,
        principal: "Principal",
        query: str | tuple[list[float], dict] | list | dict,
        top_k: int = 5,
        include_poison: bool = False,
        collection: str | None = None,
    ) -> list["SearchResult"]:
        """
        Secure hybrid search with access control filtering.
        Principal argument is REQUIRED; callers cannot supply raw Qdrant filters.
        Enforces:
          - Immediate return [] if principal has no tokens.
          - Query text trimmed and limited to 500 chars (empty returns []).
          - top_k clamped to 1..20.
          - Hybrid retrieval (dense + sparse) fused with RRF.
          - Access filter (acl_tokens MatchAny principal.tokens) applied to BOTH
            prefetches and to the final query.
          - Corpus "poison_test" excluded unless include_poison=True.
          - Plain SearchResult objects without exposing acl_tokens.
        """
        # C2: Fail closed - no tokens means no accessible documents
        if principal is None or not getattr(principal, "tokens", None):
            return []

        # C5: Clamp top_k to 1..20
        top_k = max(1, min(20, int(top_k)))

        # Resolve query vectors
        dense_vec: list[float]
        sparse_vec: dict

        if isinstance(query, str):
            query_text = query.strip()[:500]
            if not query_text:
                return []
            from app.index.embedder import DenseEmbedder, SparseEmbedder

            dense_vec = DenseEmbedder().embed_query(query_text)
            sparse_vec = SparseEmbedder().embed_sparse_query(query_text)
        elif isinstance(query, (tuple, list)) and len(query) == 2:
            dense_vec, sparse_vec = query[0], query[1]
        elif isinstance(query, dict) and "dense" in query and "sparse" in query:
            dense_vec, sparse_vec = query["dense"], query["sparse"]
        else:
            return []

        # Construct access filter
        must_conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="acl_tokens",
                match=models.MatchAny(any=list(principal.tokens)),
            )
        ]

        must_not_conditions: list[models.FieldCondition] = [
            models.FieldCondition(
                key="deleted",
                match=models.MatchValue(value=True),
            )
        ]

        if not include_poison:
            must_not_conditions.append(
                models.FieldCondition(
                    key="corpus",
                    match=models.MatchValue(value="poison_test"),
                )
            )

        access_filter = models.Filter(
            must=must_conditions,
            must_not=must_not_conditions,
        )

        name = collection or settings.QDRANT_COLLECTION
        candidate_limit = max(top_k * 4, 20)

        # C3: Dense and sparse prefetches with access filter
        dense_prefetch = models.Prefetch(
            query=dense_vec,
            using="dense",
            filter=access_filter,
            limit=candidate_limit,
        )
        sparse_prefetch = models.Prefetch(
            query=models.SparseVector(
                indices=sparse_vec["indices"],
                values=sparse_vec["values"],
            ),
            using="sparse",
            filter=access_filter,
            limit=candidate_limit,
        )

        # Outer fusion query with access filter
        response = self._client.query_points(
            collection_name=name,
            prefetch=[dense_prefetch, sparse_prefetch],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=access_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        # C4: Return plain SearchResult objects without acl_tokens
        results: list[SearchResult] = []
        for pt in response.points:
            payload = pt.payload or {}
            results.append(
                SearchResult(
                    chunk_id=str(payload.get("chunk_id", "")),
                    source_id=str(payload.get("source_id", "")),
                    file=str(payload.get("source_doc") or payload.get("source_name") or ""),
                    page=payload.get("page"),
                    corpus=str(payload.get("corpus", "main")),
                    text=str(payload.get("text", "")),
                    score=float(pt.score) if pt.score is not None else 0.0,
                )
            )

        return results
