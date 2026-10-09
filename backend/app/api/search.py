"""
Search API endpoint with permission token access control,
audit logging, rate limiting, and optional cross-encoder reranking.
"""

import hashlib
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.security.deps import get_current_user
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.security.principals import build_principal

router = APIRouter(prefix="", tags=["search"])

# In-memory sliding window rate limiter: user_id -> list of request timestamps
_user_request_timestamps: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60.0  # seconds


def check_rate_limit(user_id: str) -> bool:
    """Enforce per-user search rate limit."""
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    timestamps = [t for t in _user_request_timestamps[user_id] if t > cutoff]
    if len(timestamps) >= settings.SEARCH_RATE_LIMIT_PER_MINUTE:
        _user_request_timestamps[user_id] = timestamps
        return False
    timestamps.append(now)
    _user_request_timestamps[user_id] = timestamps
    return True


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query string")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return (1-20)")
    rerank: bool = Field(False, description="Whether to rerank results using cross-encoder")


class SearchResultItem(BaseModel):
    chunk_id: str
    source_id: str
    file: str
    page: int | None = None
    row_id: str | None = None
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    count: int
    message: str | None = None


@router.post(
    "/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def search_documents(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Execute authenticated hybrid search with row/doc level access control.
    Enforces rate limits, builds security principal fresh from database user,
    logs audit entry, and applies optional reranking.
    """
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    q_hash = hashlib.sha256(request.query.encode("utf-8")).hexdigest()[:16]
    q_len = len(request.query)

    # E4: Rate limiting
    if not check_rate_limit(user_id_str):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a minute before retrying.",
        )

    # B1 & B2: Build principal fresh from database user on this request
    principal = build_principal(current_user)

    # C1-C6: Secure hybrid search
    store = SecureStore()
    raw_results = store.search(
        principal=principal,
        query=request.query,
        top_k=request.top_k,
        include_poison=False,
    )

    # D1-D2: Optional reranking if requested or enabled globally
    should_rerank = request.rerank or settings.RERANK_ENABLED
    if should_rerank and raw_results:
        reranker = Reranker()
        final_results = reranker.rerank(
            query=request.query,
            results=raw_results,
            top_k=request.top_k,
        )
    else:
        final_results = raw_results[: request.top_k]

    elapsed = time.time() - t0
    latency_ms = round(elapsed * 1000, 2)

    # E3: Audit logging (never log document text or raw query text)
    write_audit(
        db,
        user_id=user_id_str,
        event="search",
        event_type="search",
        refused=len(final_results) == 0,
        reason_code=None if final_results else "no_results",
        latency_ms=latency_ms,
        chunk_count=len(final_results),
        admin_access=is_admin,
        question_hash=q_hash,
        question_length=q_len,
        details={
            "chunk_ids": [r.chunk_id for r in final_results],
            "count": len(final_results),
            "rerank": should_rerank,
        },
    )

    # E2: Return identical empty response for missing and forbidden topics
    if not final_results:
        return SearchResponse(
            results=[],
            count=0,
            message="No accessible results found.",
        )

    items = [
        SearchResultItem(
            chunk_id=r.chunk_id,
            source_id=r.source_id,
            file=r.file,
            page=r.page,
            row_id=getattr(r, "row_id", None),
            text=r.text,
            score=round(r.score, 6),
        )
        for r in final_results
    ]

    return SearchResponse(
        results=items,
        count=len(items),
        message=None,
    )
