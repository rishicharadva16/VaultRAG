"""
Image serving endpoint with ACL enforcement and AssetStore traversal protection.
Returns original image bytes only if the authenticated principal has permission to see the chunk.
"""

import time
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.db.models import User
from app.db.session import get_db
from app.index.store import SecureStore
from app.security.deps import get_current_user
from app.security.principals import build_principal
from app.storage.assets import asset_store

router = APIRouter(tags=["images"])

_NOT_FOUND_DETAIL = "Source chunk not found"


@router.get("/image/{chunk_id}")
def get_image(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Retrieve original image bytes for an authorized chunk.
    Returns 404 for nonexistent, forbidden, or non-image chunks (identical refusal).
    """
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")

    principal = build_principal(current_user)
    store = SecureStore()

    # ACL check inside Qdrant: SecureStore.get_chunk filters by principal.tokens MatchAny acl_tokens
    chunk = store.get_chunk(principal=principal, chunk_id=chunk_id)
    latency_ms = round((time.time() - t0) * 1000, 2)

    if chunk is None or not getattr(chunk, "file_ref", None):
        write_audit(
            db,
            user_id=user_id_str,
            event="image_read_denied",
            event_type="image_read_denied",
            refused=True,
            reason_code="not_found_or_forbidden",
            latency_ms=latency_ms,
            chunk_count=0,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "found": False},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)

    try:
        content_bytes, mime_type = asset_store.get_asset(chunk.file_ref)
    except (ValueError, FileNotFoundError):
        write_audit(
            db,
            user_id=user_id_str,
            event="image_read_denied",
            event_type="image_read_denied",
            refused=True,
            reason_code="asset_not_found",
            latency_ms=latency_ms,
            chunk_count=0,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "found": False},
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL)

    write_audit(
        db,
        user_id=user_id_str,
        event="image_read",
        event_type="image_read",
        refused=False,
        reason_code="authorized",
        latency_ms=latency_ms,
        chunk_count=1,
        admin_access=is_admin,
        details={"chunk_id": chunk_id, "found": True},
    )

    return Response(content=content_bytes, media_type=mime_type)
