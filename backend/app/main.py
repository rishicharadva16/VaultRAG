from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ask, auth, health, search
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load embedding and sparse models (and reranker if enabled) once at startup."""
    from app.index.embedder import DenseEmbedder, SparseEmbedder

    DenseEmbedder()._load()
    SparseEmbedder()._load()

    if settings.RERANK_ENABLED:
        from app.rag.reranker import Reranker

        Reranker()._load()

    yield


app = FastAPI(
    title="VaultRAG",
    description="Secure multi-modal RAG with row-level access control",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – configurable via CORS_ORIGINS in .env (comma-separated).
# Never uses "*". Never allows "null".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(ask.router)

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
