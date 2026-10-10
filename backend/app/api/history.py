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


@router.get("/history", response_model=list[HistoryItemOut], status_code=status.HTTP_200_OK)
def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HistoryItemOut]:
    """Retrieve question query history.

    - Normal user: gets only their own queries, newest first.
    - Admin: gets all users' queries, with user name and department.
    """
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (str(current_user.id) == "u_admin")

    query = db.query(AuditLog).filter(
        AuditLog.question.isnot(None),
        AuditLog.question != "",
    )

    if not is_admin:
        query = query.filter(AuditLog.user_id == str(current_user.id))

    if q and q.strip():
        query = query.filter(AuditLog.question.ilike(f"%{q.strip()}%"))

    # Order newest first
    query = query.order_by(AuditLog.created_at.desc(), AuditLog.ts.desc())

    rows = query.offset(offset).limit(limit).all()

    # Preload user mapping if admin
    user_map = {}
    if is_admin and rows:
        user_ids = {r.user_id for r in rows}
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

    results: list[HistoryItemOut] = []
    for r in rows:
        outcome_val = r.outcome or ("refused" if r.refused else "answered")
        if r.source_count is not None:
            src_count = r.source_count
        elif r.refused:
            src_count = 0
        else:
            src_count = r.chunk_count or 0

        u_name = None
        u_dept = None
        if is_admin:
            u = user_map.get(r.user_id)
            if u:
                u_name = u.name
                u_dept = u.department

        dt = r.created_at or r.ts

        results.append(
            HistoryItemOut(
                id=str(r.id),
                question=str(r.question),
                created_at=dt,
                outcome=outcome_val,
                source_count=src_count,
                user_name=u_name,
                department=u_dept,
            )
        )

    return results


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

    if not is_admin and entry.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete other users' history")

    db.delete(entry)
    db.commit()

    return {"status": "ok", "deleted_id": id}
