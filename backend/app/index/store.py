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
    row_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "file": self.file,
            "page": self.page,
            "corpus": self.corpus,
            "text": self.text,
            "score": self.score,
        }
        if self.row_id is not None:
            d["row_id"] = self.row_id
        return d


class SecureStore:
    """Single gateway to Qdrant. All access control is enforced here."""

    def __init__(self, url: str | None = None, timeout: float = 10.0):
        self._client = QdrantClient(url=url or settings.QDRANT_URL, timeout=timeout)

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
                    file=str(payload.get("file") or payload.get("table") or payload.get("source_doc") or payload.get("source_name") or ""),
                    page=payload.get("page"),
                    corpus=str(payload.get("corpus", "main")),
                    text=str(payload.get("text", "")),
                    score=float(pt.score) if pt.score is not None else 0.0,
                    row_id=payload.get("row_id") or payload.get("row_pk"),
                )
            )

        return results

    def get_chunk(
        self,
        principal: "Principal",
        chunk_id: str,
        collection: str | None = None,
    ) -> "SearchResult | None":
        """
        Fetch a single chunk by chunk_id, ONLY if the principal may see it.
        Uses the same ACL filter as search. Returns None if not found or forbidden.
        """
        if principal is None or not getattr(principal, "tokens", None):
            return None

        from app.index.schema import point_id as make_point_id

        name = collection or settings.QDRANT_COLLECTION
        pid = make_point_id(chunk_id)

        # ACL filter: same logic as search
        access_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="acl_tokens",
                    match=models.MatchAny(any=list(principal.tokens)),
                ),
                models.FieldCondition(
                    key="chunk_id",
                    match=models.MatchValue(value=chunk_id),
                ),
            ],
            must_not=[
                models.FieldCondition(
                    key="deleted",
                    match=models.MatchValue(value=True),
                ),
                models.FieldCondition(
                    key="corpus",
                    match=models.MatchValue(value="poison_test"),
                ),
            ],
        )

        try:
            points, _ = self._client.scroll(
                collection_name=name,
                scroll_filter=access_filter,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            return None

        if not points:
            return None

        pt = points[0]
        payload = pt.payload or {}
        return SearchResult(
            chunk_id=str(payload.get("chunk_id", "")),
            source_id=str(payload.get("source_id", "")),
            file=str(payload.get("file") or payload.get("table") or payload.get("source_doc") or payload.get("source_name") or ""),
            page=payload.get("page"),
            corpus=str(payload.get("corpus", "main")),
            text=str(payload.get("text", "")),
            score=0.0,
            row_id=payload.get("row_id") or payload.get("row_pk"),
        )

    # ── Admin Access Switch (In-Place Payload Update) ──────────

    def get_admin_access_status(self, collection: str | None = None) -> dict[str, int]:
        """
        Count how many points in the collection contain 'role:admin' in acl_tokens out of the total.
        Returns: {"admin_points": admin_count, "total_points": total_count}
        """
        name = collection or settings.QDRANT_COLLECTION
        total = 0
        admin_count = 0
        offset = None

        while True:
            points, next_offset = self._client.scroll(
                collection_name=name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for pt in points:
                total += 1
                tokens = (pt.payload or {}).get("acl_tokens", [])
                if "role:admin" in tokens:
                    admin_count += 1

            if next_offset is None:
                break
            offset = next_offset

        return {"admin_points": admin_count, "total_points": total}

    def set_admin_access(
        self, enabled: bool, collection: str | None = None, batch_size: int = 100,
    ) -> dict[str, int]:
        """
        Update acl_tokens in place on ALL existing points (adding or removing role:admin)
        WITHOUT re-embedding. Idempotent.
        Returns: {"scanned": scanned, "changed": changed, "already_correct": already_correct}
        """
        name = collection or settings.QDRANT_COLLECTION
        scanned = 0
        changed = 0
        already_correct = 0
        offset = None
        operations: list[models.SetPayloadOperation] = []

        while True:
            points, next_offset = self._client.scroll(
                collection_name=name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for pt in points:
                scanned += 1
                payload = pt.payload or {}
                tokens = list(payload.get("acl_tokens", []))
                has_admin = "role:admin" in tokens

                if enabled:
                    if has_admin:
                        already_correct += 1
                    else:
                        new_tokens = sorted(set(tokens) | {"role:admin"})
                        operations.append(
                            models.SetPayloadOperation(
                                set_payload=models.SetPayload(
                                    payload={"acl_tokens": new_tokens},
                                    points=[pt.id],
                                )
                            )
                        )
                        changed += 1
                else:
                    if not has_admin:
                        already_correct += 1
                    else:
                        new_tokens = sorted(set(tokens) - {"role:admin"})
                        operations.append(
                            models.SetPayloadOperation(
                                set_payload=models.SetPayload(
                                    payload={"acl_tokens": new_tokens},
                                    points=[pt.id],
                                )
                            )
                        )
                        changed += 1

            if next_offset is None:
                break
            offset = next_offset

        # Execute payload updates in batches
        if operations:
            for i in range(0, len(operations), batch_size):
                batch_ops = operations[i : i + batch_size]
                self._client.batch_update_points(
                    collection_name=name,
                    update_operations=batch_ops,
                    wait=True,
                )

        return {
            "scanned": scanned,
            "changed": changed,
            "already_correct": already_correct,
        }

