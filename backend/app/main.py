from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, health
from app.config import settings

app = FastAPI(
    title="VaultRAG",
    description="Secure multi-modal RAG with row-level access control",
    version="0.1.0",
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

# A1: /me as a top-level alias of /auth/me (same handler, same response)
app.get("/me", response_model=auth.MeResponse, tags=["auth"])(auth.me)
