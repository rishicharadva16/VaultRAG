from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.index.store import SecureStore

router = APIRouter(tags=["health"])

_store = SecureStore()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Check Postgres, Qdrant, and Ollama connectivity."""
    # Postgres
    try:
        db.execute(text("SELECT 1"))
        pg = {"status": "ok"}
    except Exception as exc:
        pg = {"status": "error", "detail": str(exc)}

    # Qdrant
    qd = _store.health()

    # Ollama LLM
    try:
        from app.llm.provider import get_llm
        llm_health = get_llm().health()
    except Exception:
        llm_health = {"status": "unavailable"}

    return {"postgres": pg, "qdrant": qd, "llm": llm_health}

