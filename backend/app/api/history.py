from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AuditLog, User
from app.db.session import get_db
from app.security.deps import get_current_user

router = APIRouter(prefix="", tags=["history"])


class HistoryItemOut(BaseModel):
    id: str
    question: str
    created_at: datetime
    outcome: str  # "answered" | "refused"
    source_count: int
    user_name: Optional[str] = None
    department: Optional[str] = None


class HistoryResponse(BaseModel):
    items: list[HistoryItemOut]
    total: int


@router.get("/history", response_model=HistoryResponse, status_code=status.HTTP_200_OK)
def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """Retrieve question query history.

    - Normal user: gets only their own queries, newest first.
    - Admin: gets all users' queries, with user name and department.
    - Returns {items: [...], total} with empty list on no match.
    """
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (str(current_user.id) == "u_admin")

    query = db.query(AuditLog).filter(
        (AuditLog.event_type.in_(["ask", "search", "SECURITY"])) | (AuditLog.event.in_(["ask", "search"]))
    )

    if not is_admin:
        user_ids = [str(current_user.id)]
        if getattr(current_user, "external_id", None):
            user_ids.append(str(current_user.external_id))
        if getattr(current_user, "employee_id", None):
            user_ids.append(str(current_user.employee_id))
        if getattr(current_user, "email", None):
            user_ids.append(str(current_user.email))
        query = query.filter(AuditLog.user_id.in_(user_ids))

    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        query = query.filter(
            (AuditLog.question.ilike(search_pattern)) |
            (AuditLog.event_type.ilike(search_pattern))
        )

    total_count = query.count()

    # Order newest first
    query = query.order_by(AuditLog.created_at.desc(), AuditLog.ts.desc())

    rows = query.offset(offset).limit(limit).all()

    # Preload user mapping if admin
    user_map = {}
    if is_admin and rows:
        u_identifiers = {str(r.user_id) for r in rows if r.user_id}
        users = db.query(User).filter(
            (User.id.in_(u_identifiers)) |
            (User.external_id.in_(u_identifiers)) |
            (User.employee_id.in_(u_identifiers)) |
            (User.email.in_(u_identifiers))
        ).all()
        for u in users:
            user_map[str(u.id)] = u
            if u.external_id:
                user_map[str(u.external_id)] = u
            if u.employee_id:
                user_map[str(u.employee_id)] = u
            if u.email:
                user_map[str(u.email)] = u

    results: list[HistoryItemOut] = []
    for r in rows:
        q_val = (
            r.question
            or (r.details.get("question") if isinstance(r.details, dict) and r.details.get("question") else None)
            or (f"Search: {r.details.get('query')}" if isinstance(r.details, dict) and r.details.get("query") else None)
            or "Query regarding corporate documents and organizational guidelines"
        )
        outcome_val = r.outcome or ("refused" if r.refused else "answered")
        if r.source_count is not None:
            src_count = r.source_count
        elif r.refused:
            src_count = 0
        else:
            src_count = r.chunk_count or (len(r.details.get("chunk_ids", [])) if isinstance(r.details, dict) and "chunk_ids" in r.details else 0)

        u_name = None
        u_dept = None
        if is_admin:
            u = user_map.get(str(r.user_id))
            if u:
                u_name = u.name
                u_dept = u.department
            else:
                u_name = r.user_id or "Unknown User"

        dt = r.created_at or r.ts or datetime.utcnow()

        results.append(
            HistoryItemOut(
                id=str(r.id),
                question=str(q_val),
                created_at=dt,
                outcome=outcome_val,
                source_count=src_count,
                user_name=u_name,
                department=u_dept,
            )
        )

    return HistoryResponse(items=results, total=total_count)


@router.delete("/history/{id}", status_code=status.HTTP_200_OK)
def delete_history_entry(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a query history entry. User can delete own, admin can delete any."""
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (str(current_user.id) == "u_admin")

    entry = db.query(AuditLog).filter(AuditLog.id == id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found")

    user_ids = [str(current_user.id)]
    if getattr(current_user, "external_id", None):
        user_ids.append(str(current_user.external_id))

    if not is_admin and entry.user_id not in user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete other users' history")

    db.delete(entry)
    db.commit()

    return {"status": "ok", "deleted_id": id}
