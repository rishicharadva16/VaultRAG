"""
Documents API endpoints for live upload, document management, and sharing (Step 6).
All access control is strictly enforced with identical 404s for forbidden and nonexistent resources.
Never exposes acl_tokens, filesystem paths, or document texts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import Document, DocumentShare, User
from app.db.session import get_db
from app.index.store import SecureStore
from app.ingestion.live_upload import (
    compute_document_tokens,
    compute_sensitive_tokens,
    detect_file_type,
    get_upload_queue,
    process_document,
    sanitize_filename,
)
from app.security.deps import get_current_user
from app.security.roles import ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["documents"])

# Sliding window rate limiter for uploads: user_id -> list of timestamps
_upload_timestamps: dict[str, list[float]] = defaultdict(list)
_TARGETS_RATE_LIMIT_PER_MINUTE = 60
_targets_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_upload_rate_limit(user_id: str) -> bool:
    """Enforce per-user uploads per hour limit."""
    now = time.time()
    cutoff = now - 3600.0  # 1 hour
    ts = [t for t in _upload_timestamps[user_id] if t > cutoff]
    if len(ts) >= settings.UPLOADS_PER_HOUR:
        _upload_timestamps[user_id] = ts
        return False
    ts.append(now)
    _upload_timestamps[user_id] = ts
    return True


def _check_targets_rate_limit(user_id: str) -> bool:
    """Rate limit sharing target queries."""
    now = time.time()
    cutoff = now - 60.0
    ts = [t for t in _targets_timestamps[user_id] if t > cutoff]
    if len(ts) >= _TARGETS_RATE_LIMIT_PER_MINUTE:
        _targets_timestamps[user_id] = ts
        return False
    ts.append(now)
    _targets_timestamps[user_id] = ts
    return True


# ── Schemas ───────────────────────────────────────────────────


class OwnerOut(BaseModel):
    id: str
    name: str


class DocumentItemOut(BaseModel):
    id: str
    filename: str
    kind: str
    status: str
    reason_code: str | None = None
    size_bytes: int
    created_at: datetime
    owner: OwnerOut
    shared_with_count: int | None = None
    can_manage: bool


class DocumentDetailOut(DocumentItemOut):
    chunk_count: int


class ShareItemOut(BaseModel):
    id: str
    grantee_type: str
    grantee_value: str
    include_sensitive: bool
    created_at: datetime
    granted_by: str


class CreateShareRequest(BaseModel):
    grantee_type: str = Field(..., pattern="^(user|role|department)$")
    value: str = Field(..., min_length=1)
    include_sensitive: bool = False


class SharingTargetsResponse(BaseModel):
    users: list[dict[str, str]]
    roles: list[str]
    departments: list[str]


# ── Helpers ───────────────────────────────────────────────────


def _user_can_access_document(doc: Document, user: User, db: Session) -> bool:
    """Check if user can view document (owner, grantee, or platform admin)."""
    if "admin" in (user.roles or []):
        return True
    if doc.owner_id == user.id:
        return True

    # Check shares
    shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).all()
    for s in shares:
        if s.grantee_type == "user" and s.grantee_value == user.id:
            return True
        elif s.grantee_type == "role" and s.grantee_value in (user.roles or []):
            return True
        elif s.grantee_type == "department" and user.department and s.grantee_value.lower() == user.department.lower():
            return True
    return False


def _get_owner_name(owner_id: str, db: Session) -> str:
    u = db.query(User).filter(User.id == owner_id).first()
    return u.name if u else "Unknown"


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    sensitive_columns: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document (PDF, image, CSV, TXT, MD).
    Ingestion runs asynchronously in a single background worker.
    """
    user_roles = current_user.roles or []
    allowed_upload_roles = settings.upload_role_list()

    # 403: Role check
    if not any(r in allowed_upload_roles for r in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload not permitted",
        )

    # 429: Rate limit check
    if not _check_upload_rate_limit(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded. Please try again later.",
        )

    # Read content
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File cannot be empty",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size limit of {settings.MAX_UPLOAD_MB} MB",
        )

    # Magic byte type detection
    try:
        kind, ext = detect_file_type(content, filename_hint=file.filename or "")
    except ValueError as e:
        if str(e) == "empty_file":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File cannot be empty")
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file format")

    # Parse sensitive columns if given
    sens_cols_list: list[str] = []
    if sensitive_columns:
        try:
            parsed = json.loads(sensitive_columns)
            if isinstance(parsed, list):
                sens_cols_list = [str(c).strip() for c in parsed if str(c).strip()]
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sensitive_columns format")

    # Deduplication: same owner and same sha256
    file_sha256 = hashlib.sha256(content).hexdigest()
    existing = db.query(Document).filter(
        Document.owner_id == current_user.id,
        Document.sha256 == file_sha256,
        Document.deleted_at.is_(None),
    ).first()

    if existing:
        response.status_code = status.HTTP_200_OK
        return {"id": existing.id, "status": existing.status}

    # Create new document
    sanitized_name = sanitize_filename(file.filename or f"uploaded{ext}")
    import uuid
    doc_id = str(uuid.uuid4())
    source_id = f"upl:{doc_id}"

    # Write original to storage
    storage_root = settings.storage_path()
    doc_dir = storage_root / "uploads" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    orig_path = doc_dir / f"original{ext}"
    orig_path.write_bytes(content)

    doc = Document(
        id=doc_id,
        source_id=source_id,
        filename=sanitized_name,
        kind=kind,
        size_bytes=len(content),
        sha256=file_sha256,
        owner_id=current_user.id,
        status="queued",
        reason_code=None,
        chunk_count=0,
        sensitive_columns=sens_cols_list,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Audit upload
    write_audit(
        db,
        user_id=current_user.id,
        event="upload",
        event_type="upload",
        refused=False,
        reason_code="QUEUED",
        details={
            "doc_id": doc_id,
            "kind": kind,
            "size_bytes": len(content),
        },
    )

    # Enqueue background ingestion
    get_upload_queue().put_nowait(doc_id)

    return {"id": doc_id, "status": "queued"}


@router.get("/documents", response_model=list[DocumentItemOut])
def list_documents(
    scope: str = Query("mine", pattern="^(mine|shared|all)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List documents according to scope (mine, shared, all)."""
    user_is_admin = "admin" in (current_user.roles or [])

    if scope == "all":
        if not user_is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        query = db.query(Document).filter(Document.deleted_at.is_(None))
    elif scope == "mine":
        query = db.query(Document).filter(
            Document.owner_id == current_user.id,
            Document.deleted_at.is_(None),
        )
    else:  # shared
        # Find doc IDs shared with caller where caller is not owner
        user_roles = current_user.roles or []
        user_dept = current_user.department

        share_query = db.query(DocumentShare.document_id).distinct()
        conditions = [
            (DocumentShare.grantee_type == "user") & (DocumentShare.grantee_value == current_user.id),
        ]
        if user_roles:
            conditions.append((DocumentShare.grantee_type == "role") & (DocumentShare.grantee_value.in_(user_roles)))
        if user_dept:
            conditions.append((DocumentShare.grantee_type == "department") & (DocumentShare.grantee_value.ilike(user_dept)))

        from sqlalchemy import or_
        matching_doc_ids = [r[0] for r in share_query.filter(or_(*conditions)).all()]

        query = db.query(Document).filter(
            Document.id.in_(matching_doc_ids),
            Document.owner_id != current_user.id,
            Document.deleted_at.is_(None),
        )

    docs = query.order_by(Document.created_at.desc()).all()
    results: list[DocumentItemOut] = []

    for d in docs:
        is_owner = (d.owner_id == current_user.id)
        can_manage = is_owner or user_is_admin

        shared_count: int | None = None
        if can_manage:
            shared_count = db.query(DocumentShare).filter(DocumentShare.document_id == d.id).count()

        results.append(
            DocumentItemOut(
                id=d.id,
                filename=d.filename,
                kind=d.kind,
                status=d.status,
                reason_code=d.reason_code,
                size_bytes=d.size_bytes,
                created_at=d.created_at,
                owner=OwnerOut(id=d.owner_id, name=_get_owner_name(d.owner_id, db)),
                shared_with_count=shared_count,
                can_manage=can_manage,
            )
        )

    return results


@router.get("/documents/{doc_id}", response_model=DocumentDetailOut)
def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve document metadata. Returns identical 404 for nonexistent or forbidden."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
    if not doc or not _user_can_access_document(doc, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_is_admin = "admin" in (current_user.roles or [])
    is_owner = (doc.owner_id == current_user.id)
    can_manage = is_owner or user_is_admin

    shared_count: int | None = None
    if can_manage:
        shared_count = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).count()

    return DocumentDetailOut(
        id=doc.id,
        filename=doc.filename,
        kind=doc.kind,
        status=doc.status,
        reason_code=doc.reason_code,
        size_bytes=doc.size_bytes,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        owner=OwnerOut(id=doc.owner_id, name=_get_owner_name(doc.owner_id, db)),
        shared_with_count=shared_count,
        can_manage=can_manage,
    )


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete document and its chunks. Owner or admin only."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_is_admin = "admin" in (current_user.roles or [])
    if doc.owner_id != current_user.id and not user_is_admin:
        # Grantees get identical 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Soft delete in DB
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()

    # Remove points from Qdrant
    store = SecureStore()
    store.delete_by_source_id(doc.source_id)

    # Remove storage folder and cached renders
    storage_root = settings.storage_path()
    doc_dir = storage_root / "uploads" / doc.id
    if doc_dir.exists():
        shutil.rmtree(doc_dir, ignore_errors=True)

    cache_dir = Path(__file__).resolve().parent.parent / "data" / "cache" / "page_renders"
    if cache_dir.exists():
        for p in cache_dir.glob(f"{doc.sha256[:24]}*"):
            try:
                p.unlink()
            except Exception:
                pass

    # Audit delete
    write_audit(
        db,
        user_id=current_user.id,
        event="delete",
        event_type="delete",
        refused=False,
        reason_code="DELETED",
        details={"doc_id": doc.id, "source_id": doc.source_id},
    )
    return None


# ── Document Sharing ──────────────────────────────────────────


@router.get("/documents/{doc_id}/shares", response_model=list[ShareItemOut])
def get_document_shares(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List document shares. Owner or admin only; everyone else gets identical 404."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_is_admin = "admin" in (current_user.roles or [])
    if doc.owner_id != current_user.id and not user_is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).all()
    return [
        ShareItemOut(
            id=s.id,
            grantee_type=s.grantee_type,
            grantee_value=s.grantee_value,
            include_sensitive=s.include_sensitive,
            created_at=s.created_at,
            granted_by=s.granted_by,
        )
        for s in shares
    ]


@router.post("/documents/{doc_id}/shares", response_model=ShareItemOut, status_code=status.HTTP_201_CREATED)
def create_document_share(
    doc_id: str,
    body: CreateShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a share grant to document. Updates Qdrant ACL immediately before returning."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_is_admin = "admin" in (current_user.roles or [])
    if doc.owner_id != current_user.id and not user_is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Validate grantee
    if body.grantee_type == "user":
        target_user = db.query(User).filter(User.id == body.value).first()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")
    elif body.grantee_type == "role":
        if body.value not in ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {body.value}")

    # Check existing share
    existing = db.query(DocumentShare).filter(
        DocumentShare.document_id == doc.id,
        DocumentShare.grantee_type == body.grantee_type,
        DocumentShare.grantee_value == body.value,
    ).first()

    if existing:
        existing.include_sensitive = body.include_sensitive
        share = existing
    else:
        import uuid
        share = DocumentShare(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            grantee_type=body.grantee_type,
            grantee_value=body.value,
            include_sensitive=body.include_sensitive,
            granted_by=current_user.id,
        )
        db.add(share)

    db.commit()
    db.refresh(share)

    # Recompute ACL in Qdrant
    all_shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).all()
    base_tokens = compute_document_tokens(doc, all_shares)
    sens_tokens = compute_sensitive_tokens(doc, all_shares)

    store = SecureStore()
    store.set_acl_by_source_id(doc.source_id, tokens=base_tokens, sensitive_tokens=sens_tokens)

    # Audit
    write_audit(
        db,
        user_id=current_user.id,
        event="share",
        event_type="share",
        refused=False,
        reason_code="SHARE_GRANTED",
        details={
            "doc_id": doc.id,
            "grantee_type": body.grantee_type,
            "grantee_value": body.value,
            "include_sensitive": body.include_sensitive,
        },
    )

    return ShareItemOut(
        id=share.id,
        grantee_type=share.grantee_type,
        grantee_value=share.grantee_value,
        include_sensitive=share.include_sensitive,
        created_at=share.created_at,
        granted_by=share.granted_by,
    )


@router.delete("/documents/{doc_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_share(
    doc_id: str,
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a document share. Removes access in Qdrant immediately before returning."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.deleted_at.is_(None)).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    user_is_admin = "admin" in (current_user.roles or [])
    if doc.owner_id != current_user.id and not user_is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    share = db.query(DocumentShare).filter(
        DocumentShare.id == share_id,
        DocumentShare.document_id == doc.id,
    ).first()

    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    grantee_type = share.grantee_type
    grantee_val = share.grantee_value

    db.delete(share)
    db.commit()

    # Recompute ACL in Qdrant immediately
    all_shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).all()
    base_tokens = compute_document_tokens(doc, all_shares)
    sens_tokens = compute_sensitive_tokens(doc, all_shares)

    store = SecureStore()
    store.set_acl_by_source_id(doc.source_id, tokens=base_tokens, sensitive_tokens=sens_tokens)

    # Audit
    write_audit(
        db,
        user_id=current_user.id,
        event="unshare",
        event_type="unshare",
        refused=False,
        reason_code="SHARE_REVOKED",
        details={
            "doc_id": doc.id,
            "share_id": share_id,
            "grantee_type": grantee_type,
            "grantee_value": grantee_val,
        },
    )
    return None


@router.get("/sharing/targets", response_model=SharingTargetsResponse)
def get_sharing_targets(
    q: str = Query("", max_length=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search available users, roles, and departments to share with.
    Rate-limited. Does not leak emails or other sensitive attributes.
    """
    if not _check_targets_rate_limit(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a moment before searching again.",
        )

    users_query = db.query(User).filter(User.active.is_(True))
    if q.strip():
        users_query = users_query.filter(User.name.ilike(f"%{q.strip()}%"))

    users_list = [
        {"id": u.id, "name": u.name, "department": u.department or ""}
        for u in users_query.limit(20).all()
    ]

    all_roles = [r for r in sorted(ROLES) if r != "admin"]
    if q.strip():
        filtered_roles = [r for r in all_roles if q.strip().lower() in r.lower()]
    else:
        filtered_roles = all_roles

    depts_query = db.query(User.department).filter(User.department.isnot(None)).distinct()
    all_depts = sorted({r[0] for r in depts_query.all() if r[0]})
    if q.strip():
        filtered_depts = [d for d in all_depts if q.strip().lower() in d.lower()]
    else:
        filtered_depts = all_depts

    return SharingTargetsResponse(
        users=users_list,
        roles=filtered_roles,
        departments=filtered_depts,
    )
