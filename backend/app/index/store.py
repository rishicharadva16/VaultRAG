"""
Secure vector store gateway.

RULE: This module is the ONLY code in the project allowed to import qdrant_client.
      All other modules must go through SecureStore to interact with Qdrant.
      This ensures every query passes through ACL filtering.

PAYLOAD DESIGN (for later steps):
    Each Qdrant point payload will contain:
    {
        "text":            str,          # chunk text
        "doc_id":          str,          # source document id
        "page":            int,          # page number in source
        "owner_id":        str,          # uploader user id
        "allowed_roles":   list[str],    # roles that may see this chunk
        "allowed_users":   list[str],    # specific user ids with access
        "classification":  int,          # clearance level required (1-3)
        "is_public":       bool,         # if True, visible to everyone
    }
    Qdrant payloads accept lists natively, so allowed_roles and allowed_users
    are stored as plain JSON arrays – no encoding tricks needed.

COLLECTION DESIGN (for later steps):
    The collection will use named vectors:
      - "dense"  : bge-m3 embeddings (dim 1024)
      - "sparse" : BM25 via fastembed (sparse vectors)
    Payload indexes will be created on:
      allowed_roles, allowed_users, owner_id, classification, is_public, doc_id
"""

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings


class SecureStore:
    """Single gateway to Qdrant. All access control is enforced here."""

    def __init__(self, url: str | None = None):
        self._client = QdrantClient(url=url or settings.QDRANT_URL)

    def health(self) -> dict:
        """Return {"status": "ok"} or {"status": "error", "detail": ...}."""
        try:
            # A simple connectivity check
            self._client.get_collections()
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    # TODO [Step 2 – Ingestion]: add upsert_chunks() method
    #   - Accepts chunks with payload as described above
    #   - Creates/ensures the collection with named dense + sparse vectors
    #   - Creates payload indexes on first run

    # TODO [Step 3 – Search]: add search() method
    #   - MUST take a required `acl_filter` argument with NO default value
    #   - Fail closed: if acl_filter is None or missing, raise an error immediately
    #   - Build a Qdrant Filter from acl_filter and apply it to every query
    #   - Support hybrid search (dense + sparse with RRF fusion)

    # TODO [Step 4 – Delete]: add delete_by_doc() method
    #   - Delete all points for a given doc_id, only if the caller owns the doc
