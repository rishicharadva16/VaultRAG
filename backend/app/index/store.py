"""
Secure vector store gateway.

RULE: This module is the ONLY code in the project allowed to import qdrant_client.
      All other modules must go through SecureStore to interact with Qdrant.
      This ensures every query passes through ACL filtering.

PAYLOAD DESIGN:
    Qdrant payloads accept lists natively, so allowed_roles and allowed_users
    are stored as plain JSON arrays – no encoding tricks needed.
"""

from qdrant_client import QdrantClient, models

from app.config import settings

# Payload index definitions: (field_name, schema_type)
_KEYWORD_FIELDS = ["allowed_roles", "allowed_users", "owner_id", "doc_id", "source_type"]
_INTEGER_FIELDS = ["classification"]
_BOOL_FIELDS = ["is_public", "deleted"]


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

    def delete_collection(self, collection: str) -> None:
        """Delete a collection entirely (for test cleanup)."""
        self._client.delete_collection(collection)

    # ── Search (Step 3) ───────────────────────────────────────

    # TODO [Step 3 – Search]: add search() method
    #   - MUST take a required `acl_filter` argument with NO default value
    #   - Fail closed: if acl_filter is None or missing, raise an error immediately
    #   - Build a Qdrant Filter from acl_filter and apply it to every query
    #   - Support hybrid search (dense + sparse with RRF fusion)
