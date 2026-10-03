from sqlalchemy.orm import Session

from app.db.models import AuditLog


def write_audit(db: Session, *, user_id: str, event: str, details: dict | None = None) -> None:
    db.add(AuditLog(user_id=user_id, event=event, details=details))
    db.commit()
