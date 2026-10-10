from sqlalchemy.orm import Session

from app.db.models import AuditLog


def write_audit(
    db: Session,
    *,
    user_id: str,
    event: str | None = None,
    event_type: str | None = None,
    refused: bool | None = None,
    reason_code: str | None = None,
    latency_ms: float | None = None,
    chunk_count: int | None = None,
    admin_access: bool = False,
    question_hash: str | None = None,
    question_length: int | None = None,
    details: dict | None = None,
    question: str | None = None,
    outcome: str | None = None,
    source_count: int | None = None,
) -> AuditLog:
    ev = event or event_type or "unknown"
    ev_type = event_type or event or "unknown"
    log_entry = AuditLog(
        user_id=user_id,
        event=ev,
        event_type=ev_type,
        refused=refused,
        reason_code=reason_code,
        latency_ms=latency_ms,
        chunk_count=chunk_count,
        admin_access=admin_access,
        question_hash=question_hash,
        question_length=question_length,
        details=details,
        question=question,
        outcome=outcome,
        source_count=source_count,
    )
    db.add(log_entry)
    db.commit()
    return log_entry
