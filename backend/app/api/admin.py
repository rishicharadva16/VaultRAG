from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.db.models import User, DocumentShare
from app.db.session import get_db
from app.security.deps import require_admin
from app.security.passwords import (
    PasswordTooLong, PasswordTooShort,
    hash_password, validate_password,
)
from app.security.roles import ROLES
from app.security.users import get_user, get_user_by_email

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    department: str | None = None
    employee_id: str | None = None
    roles: list[str] = []
    external_id: str | None = None


class PatchUserRequest(BaseModel):
    name: str | None = None
    department: str | None = None
    is_active: bool | None = None
    shown_in_demo: bool | None = None
    password: str | None = None


class UpdateRolesRequest(BaseModel):
    roles: list[str]


class UpdateActiveRequest(BaseModel):
    active: bool


class AdminUserOut(BaseModel):
    id: str
    name: str
    email: str
    department: str | None = None
    employee_id: str | None = None
    is_active: bool
    shown_in_demo: bool
    is_admin: bool
    roles: list[str] = []


UserOut = AdminUserOut


def _to_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        department=user.department,
        employee_id=user.employee_id,
        is_active=user.active,
        shown_in_demo=bool(getattr(user, "shown_in_demo", False)),
        is_admin="admin" in (user.roles or []),
        roles=user.roles or [],
    )


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        validate_password(body.password)
    except (PasswordTooShort, PasswordTooLong) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if get_user_by_email(db, body.email):
        # Step 5e requirement: duplicate email gives 422
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Email already registered")

    # Step 5e: Role is always employee
    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        roles=["employee"],
        employee_id=body.employee_id,
        department=body.department,
        external_id=body.external_id,
        active=True,
        shown_in_demo=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.create_user",
        details={
            "target": user.id,
            "email": user.email,
            "roles": user.roles,
            "employee_id": user.employee_id,
            "department": user.department,
        },
    )
    return _to_out(user)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return [_to_out(u) for u in db.query(User).all()]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user(
    user_id: str,
    body: PatchUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Admin cannot deactivate themselves
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot deactivate themselves")

    changes = {}
    if body.name is not None:
        user.name = body.name
        changes["name"] = body.name
    if body.department is not None:
        user.department = body.department
        changes["department"] = body.department
    if body.is_active is not None:
        user.active = body.is_active
        changes["is_active"] = body.is_active
    if body.shown_in_demo is not None:
        user.shown_in_demo = body.shown_in_demo
        changes["shown_in_demo"] = body.shown_in_demo
    if body.password is not None:
        try:
            validate_password(body.password)
        except (PasswordTooShort, PasswordTooLong) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        user.password_hash = hash_password(body.password)
        changes["password_updated"] = True

    # Nobody can be promoted to admin through the API
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.patch_user",
        details={"target": user_id, "changes": changes},
    )
    return _to_out(user)


@router.put("/users/{user_id}/roles", response_model=AdminUserOut)
def update_roles(
    user_id: str,
    body: UpdateRolesRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.roles = body.roles
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.update_roles",
        details={"target": user_id, "new": {"roles": user.roles}},
    )
    return _to_out(user)


@router.put("/users/{user_id}/active", response_model=AdminUserOut)
def update_active(
    user_id: str,
    body: UpdateActiveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id and body.active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot deactivate themselves")

    old_active = user.active
    user.active = body.active
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        user_id=admin.id,
        event="admin.update_active",
        details={"target": user_id, "old_active": old_active, "new_active": user.active},
    )
    return _to_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot delete themselves")

    db.query(DocumentShare).filter(
        (DocumentShare.grantee_type == "user") & (DocumentShare.grantee_value == user.id)
    ).delete(synchronize_session=False)

    db.delete(user)
    db.commit()

    write_audit(
        db,
        user_id=admin.id,
        event="admin.delete_user",
        details={"target": user_id, "deleted_user_email": user.email},
    )
    return None


# ── Step 6 Admin Monitoring Endpoints ─────────────────────────

from datetime import datetime, timedelta, timezone
from fastapi import Query
from app.db.models import AuditLog, Document, DocumentShare


class AuditSummaryTotals(BaseModel):
    asks: int
    searches: int
    refusals: int
    refusal_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    uploads: int
    active_users: int


class AuditSummaryOut(BaseModel):
    days: int
    totals: AuditSummaryTotals
    per_day_series: list[dict[str, Any]]
    counts_by_reason_code: dict[str, int]
    top_users: list[dict[str, Any]]


class QueryItemOut(BaseModel):
    time: datetime
    user_name: str
    event_type: str
    refused: bool | None = None
    reason_code: str | None = None
    latency_ms: float | None = None
    chunk_count: int | None = None
    admin_access: bool = False
    question_hash: str | None = None
    question_length: int | None = None


class AdminUploadItemOut(BaseModel):
    id: str
    filename: str
    kind: str
    status: str
    size_bytes: int
    owner: dict[str, str]
    shared_with_count: int
    deleted: bool
    created_at: datetime
    updated_at: datetime


@router.get("/audit/summary", response_model=AuditSummaryOut)
def get_audit_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin dashboard summary metrics over the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    logs = (
        db.query(AuditLog)
        .filter((AuditLog.created_at >= cutoff) | (AuditLog.ts >= cutoff))
        .all()
    )

    asks = 0
    searches = 0
    refusals = 0
    uploads = 0
    user_ids: set[str] = set()
    user_query_counts: dict[str, int] = defaultdict(int)
    reason_counts: dict[str, int] = defaultdict(int)
    latencies: list[float] = []
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: {"asks": 0, "searches": 0, "refusals": 0, "uploads": 0})

    for row in logs:
        ev = (row.event_type or row.event or "").lower()
        t = row.created_at or row.ts or datetime.now(timezone.utc)
        day_str = t.strftime("%Y-%m-%d")

        if row.user_id:
            user_ids.add(row.user_id)

        if ev == "ask":
            asks += 1
            per_day[day_str]["asks"] += 1
            user_query_counts[row.user_id] += 1
        elif ev == "search":
            searches += 1
            per_day[day_str]["searches"] += 1
            user_query_counts[row.user_id] += 1
        elif ev in ("upload", "upload_ingest", "ingest"):
            uploads += 1
            per_day[day_str]["uploads"] += 1

        if row.refused:
            refusals += 1
            per_day[day_str]["refusals"] += 1

        if row.reason_code:
            reason_counts[row.reason_code] += 1

        if row.latency_ms is not None and row.latency_ms > 0:
            latencies.append(float(row.latency_ms))

    # Calculate rates and percentiles
    total_queries = asks + searches
    refusal_rate = round(refusals / max(1, total_queries), 4)

    if latencies:
        latencies.sort()
        avg_lat = round(sum(latencies) / len(latencies), 2)
        p95_idx = int(0.95 * len(latencies))
        p95_lat = round(latencies[min(p95_idx, len(latencies) - 1)], 2)
    else:
        avg_lat = 0.0
        p95_lat = 0.0

    # User names mapping
    user_names = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_query_counts.keys())).all()} if user_query_counts else {}
    for u in db.query(User).filter(User.external_id.in_(user_query_counts.keys())).all():
        user_names[u.external_id] = u.name

    top_users = [
        {"name": user_names.get(uid, uid), "count": count}
        for uid, count in sorted(user_query_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    series = [
        {"date": d, **counts}
        for d, counts in sorted(per_day.items(), key=lambda x: x[0])
    ]

    write_audit(
        db,
        user_id=admin.id,
        event="admin.audit_summary",
        event_type="admin.audit_summary",
        admin_access=True,
        details={"days": days},
    )

    return AuditSummaryOut(
        days=days,
        totals=AuditSummaryTotals(
            asks=asks,
            searches=searches,
            refusals=refusals,
            refusal_rate=refusal_rate,
            avg_latency_ms=avg_lat,
            p95_latency_ms=p95_lat,
            uploads=uploads,
            active_users=len(user_ids),
        ),
        per_day_series=series,
        counts_by_reason_code=dict(reason_counts),
        top_users=top_users,
    )


@router.get("/queries", response_model=list[QueryItemOut])
def get_admin_queries(
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Paginated audit log for queries (asks and searches).
    NEVER returns raw question or answer text.
    """
    query = (
        db.query(AuditLog)
        .filter(AuditLog.event_type.in_(["ask", "search"]))
    )
    if before:
        query = query.filter((AuditLog.created_at < before) | (AuditLog.ts < before))

    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.ts.desc()).limit(limit).all()

    # Preload user names
    user_ids = {r.user_id for r in rows if r.user_id}
    users = db.query(User).filter((User.id.in_(user_ids)) | (User.external_id.in_(user_ids))).all()
    name_map = {}
    for u in users:
        name_map[u.id] = u.name
        if u.external_id:
            name_map[u.external_id] = u.name

    write_audit(
        db,
        user_id=admin.id,
        event="admin.queries",
        event_type="admin.queries",
        admin_access=True,
        details={"limit": limit},
    )

    results = []
    for r in rows:
        t = r.created_at or r.ts or datetime.now(timezone.utc)
        results.append(
            QueryItemOut(
                time=t,
                user_name=name_map.get(r.user_id, r.user_id or "Unknown"),
                event_type=r.event_type or r.event or "unknown",
                refused=r.refused,
                reason_code=r.reason_code,
                latency_ms=r.latency_ms,
                chunk_count=r.chunk_count,
                admin_access=bool(r.admin_access),
                question_hash=r.question_hash,
                question_length=r.question_length,
            )
        )
    return results


@router.get("/uploads", response_model=list[AdminUploadItemOut])
def get_admin_uploads(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all documents (active and deleted) for platform administration."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()

    owner_ids = {d.owner_id for d in docs}
    owners = db.query(User).filter(User.id.in_(owner_ids)).all()
    owner_map = {u.id: u.name for u in owners}

    results = []
    for d in docs:
        s_count = db.query(DocumentShare).filter(DocumentShare.document_id == d.id).count()
        results.append(
            AdminUploadItemOut(
                id=d.id,
                filename=d.filename,
                kind=d.kind,
                status=d.status,
                size_bytes=d.size_bytes,
                owner={"id": d.owner_id, "name": owner_map.get(d.owner_id, "Unknown")},
                shared_with_count=s_count,
                deleted=d.deleted_at is not None,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
        )

    write_audit(
        db,
        user_id=admin.id,
        event="admin.uploads",
        event_type="admin.uploads",
        admin_access=True,
        details={"total_documents": len(docs)},
    )

    return results

