from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ask, auth, health, search, images, source, documents, history
from app.config import settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.ingestion.live_upload import start_upload_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models, recover interrupted documents, and launch upload worker."""
    from app.index.embedder import DenseEmbedder, SparseEmbedder

    DenseEmbedder()._load()
    SparseEmbedder()._load()

    if settings.RERANK_ENABLED:
        from app.rag.reranker import Reranker

        Reranker()._load()

    # Step 6: Mark interrupted documents on startup
    try:
        with SessionLocal() as db:
            interrupted = db.query(Document).filter(Document.status == "processing").all()
            for doc in interrupted:
                doc.status = "failed"
                doc.reason_code = "interrupted"
            if interrupted:
                db.commit()
    except Exception:
        pass

    # Ensure history columns on audit_log
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS question VARCHAR;"))
            db.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS outcome VARCHAR;"))
            db.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS source_count INTEGER;"))
            db.commit()
    except Exception:
        pass

    # Start single sequential upload worker
    await start_upload_worker()

    yield


app = FastAPI(
    title="VaultRAG",
    description="Secure multi-modal RAG with row-level access control",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – configurable via CORS_ORIGINS in .env (comma-separated).
# Allows GET, POST, DELETE, PUT, PATCH, OPTIONS for multipart uploads and management.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(images.router)
app.include_router(source.router)
app.include_router(documents.router)
app.include_router(history.router)

# A1: /me as a top-level alias of /auth/me (same handler, same response)
app.get("/me", response_model=auth.MeResponse, tags=["auth"])(auth.me)


@app.get("/", tags=["system"])
def root():
    """Root endpoint confirming API status and linking to documentation."""
    return {
        "status": "ok",
        "message": "VaultRAG API is running",
        "docs": "/docs",
        "health": "/health",
        "version": "0.1.0",
    }
