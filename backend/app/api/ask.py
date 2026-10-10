"""
POST /ask endpoint – grounded answers with verified citations.
GET /citation/{chunk_id} – retrieve a single chunk's text with ACL enforcement.
"""

import hashlib
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.llm.provider import LLMTimeout
from app.rag.answer import REFUSAL_TEXT, AnswerResult, answer_question
from app.security.deps import get_current_user
from app.security.principals import build_principal

router = APIRouter(prefix="", tags=["ask"])

# Rate limiter for /ask (separate from /search, lower default)
_ask_timestamps: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60.0


def _check_ask_rate(user_id: str) -> bool:
    now = time.time()
    cutoff = now - _RATE_WINDOW
    ts = [t for t in _ask_timestamps[user_id] if t > cutoff]
    if len(ts) >= settings.ASK_RATE_LIMIT_PER_MINUTE:
        _ask_timestamps[user_id] = ts
        return False
    ts.append(now)
    _ask_timestamps[user_id] = ts
    return True


# ── Request / Response models ─────────────────────────────────


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Question to answer")
    top_k: int = Field(5, ge=1, le=20, description="Max context chunks")
    source_ids: list[str] | None = Field(None, description="Optional list of source_ids to filter by (max 10)")


class HighlightOut(BaseModel):
    start: int
    end: int


class CitationOut(BaseModel):
    id: int
    chunk_id: str
    source_id: str
    file: str
    page: int | None = None
    row_id: str | None = None
    kind: str | None = None
    ocr_confidence: float | None = None
    boxes: list[dict] | None = None
    snippet: str
    highlights: list[HighlightOut] = []
    highlight_text: str = ""


class AskResponse(BaseModel):
    answer: str
    refused: bool
    verified: bool
    citations: list[CitationOut]


class ChunkResponse(BaseModel):
    chunk_id: str
    source_id: str
    file: str
    page: int | None = None
    row_id: str | None = None
    kind: str | None = None
    text: str
    boxes: list[dict] | None = None
    image_width: int | None = None
    image_height: int | None = None
    ocr_confidence: float | None = None


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/ask", response_model=AskResponse, status_code=status.HTTP_200_OK)
def ask(
    body: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AskResponse:
    """Answer a question using grounded RAG with verified citations."""
    user_id_str = str(current_user.id)
    t0 = time.time()

    # Rate limiting
    if not _check_ask_rate(user_id_str):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a minute before retrying.",
        )

    principal = build_principal(current_user)

    try:
        result: AnswerResult = answer_question(
            principal=principal,
            question=body.question,
            top_k=body.top_k,
            source_ids=body.source_ids,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must be 1-500 characters.",
        )
    except LLMTimeout:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable. Please try again later.",
        )

    elapsed = time.time() - t0
    latency_ms = round(elapsed * 1000, 2)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    q_hash = hashlib.sha256(body.question.encode("utf-8")).hexdigest()[:16]
    q_len = len(body.question)

    outcome_val = "refused" if result.refused else "answered"
    src_cnt = len(result.citations) if not result.refused else 0

    # Audit (never log chunk text or answer text; question and metadata only)
    try:
        write_audit(
            db,
            user_id=user_id_str,
            event="ask" if not result._reason == "output_guard" else "SECURITY",
            event_type="ask" if not result._reason == "output_guard" else "SECURITY",
            refused=result.refused,
            reason_code=result._reason,
            latency_ms=latency_ms,
            chunk_count=len(result.citations),
            admin_access=is_admin,
            question_hash=q_hash,
            question_length=q_len,
            question=body.question,
            outcome=outcome_val,
            source_count=src_cnt,
            details={
                "chunk_ids": [c.chunk_id for c in result.citations],
                "refused": result.refused,
                "reason": result._reason,
                "latency_s": round(elapsed, 2),
            },
        )

        # Security events get a separate audit entry
        if result._reason == "output_guard":
            write_audit(
                db,
                user_id=user_id_str,
                event="SECURITY",
                event_type="SECURITY",
                refused=True,
                reason_code="output_guard",
                latency_ms=latency_ms,
                chunk_count=0,
                admin_access=is_admin,
                question_hash=q_hash,
                question_length=q_len,
                details={
                    "reason": "output_guard",
                    "action": "blocked",
                },
            )
    except Exception:
        # Logging error must never break the chat
        pass

    return AskResponse(
        answer=result.answer,
        refused=result.refused,
        verified=result.verified,
        citations=[
            CitationOut(
                id=c.id,
                chunk_id=c.chunk_id,
                source_id=c.source_id,
                file=c.file,
                page=c.page,
                row_id=c.row_id,
                kind=getattr(c, "kind", None),
                ocr_confidence=getattr(c, "ocr_confidence", None),
                boxes=getattr(c, "boxes", None),
                snippet=c.snippet,
                highlights=[HighlightOut(start=h.start, end=h.end) for h in c.highlights],
                highlight_text=c.highlight_text,
            )
            for c in result.citations
        ],
    )


_NOT_FOUND = {"detail": "Chunk not found"}


@router.get("/citation/{chunk_id}", response_model=ChunkResponse)
def get_citation(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChunkResponse:
    """Retrieve a single chunk's text. Returns 404 for non-existent AND forbidden chunks."""
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    principal = build_principal(current_user)

    from app.index.store import SecureStore

    store = SecureStore()
    chunk = store.get_chunk(principal=principal, chunk_id=chunk_id)
    latency_ms = round((time.time() - t0) * 1000, 2)

    # Audit (never log document text)
    write_audit(
        db,
        user_id=user_id_str,
        event="citation",
        event_type="citation",
        refused=chunk is None,
        reason_code="not_found_or_forbidden" if chunk is None else None,
        latency_ms=latency_ms,
        chunk_count=1 if chunk is not None else 0,
        admin_access=is_admin,
        details={
            "chunk_id": chunk_id,
            "found": chunk is not None,
        },
    )

    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    return ChunkResponse(
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        file=chunk.file,
        page=chunk.page,
        row_id=chunk.row_id,
        kind=chunk.kind,
        text=chunk.text,
        boxes=chunk.boxes,
        image_width=chunk.image_width,
        image_height=chunk.image_height,
        ocr_confidence=chunk.ocr_confidence,
    )
