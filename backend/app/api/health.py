from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.index.store import SecureStore

router = APIRouter(tags=["health"])

_store = SecureStore()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Check Postgres and Qdrant connectivity."""
    # Postgres
    try:
        db.execute(text("SELECT 1"))
        pg = {"status": "ok"}
    except Exception as exc:
        pg = {"status": "error", "detail": str(exc)}

    # Qdrant
    qd = _store.health()

    return {"postgres": pg, "qdrant": qd}
