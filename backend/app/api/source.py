"""
Source Viewer endpoints for VaultRAG.
Supports viewing verified source pages (PDFs and images) with highlighted line rectangles,
rendering page images with access control enforcement, and listing readable pages.
Enforces fail-closed semantics: forbidden and nonexistent chunks return identical 404s.
Never returns acl_tokens or absolute filesystem paths. Never logs sensitive text.
"""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.db.models import User
from app.db.session import get_db
from app.index.store import SecureStore
from app.security.deps import get_current_user
from app.security.principals import build_principal
from app.storage.assets import asset_store
from app.storage.page_renderer import (
    compute_pdf_highlight_rects,
    get_pdf_page_count,
    render_pdf_page,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/source", tags=["source"])

_NOT_FOUND = {"detail": "Chunk not found"}


# ── Response Models ───────────────────────────────────────────


class RectOut(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)


class SourceViewResponse(BaseModel):
    kind: str  # "pdf_text" | "image" | "db_row" | "text"
    file: str
    page: int | None = None
    row_id: str | None = None
    page_width: float | None = None
    page_height: float | None = None
    rects: list[RectOut] = []
    match: Literal["exact", "partial", "none"]
    text: str
    page_image_url: str | None = None


class SourcePagesResponse(BaseModel):
    page_count: int
    readable_pages: list[int]


# ── Helper functions ──────────────────────────────────────────


def _parse_highlight_param(hl: str | None) -> list[tuple[int, int]]:
    """Parse comma-separated 'start-end' highlight offset ranges."""
    if not hl:
        return []
    spans: list[tuple[int, int]] = []
    for part in hl.split(","):
        part = part.strip()
        if not part or "-" not in part:
            continue
        try:
            s_str, e_str = part.split("-", 1)
            s_val = int(s_str.strip())
            e_val = int(e_str.strip())
            if s_val < e_val:
                spans.append((s_val, e_val))
        except ValueError:
            continue
    return spans


def _resolve_pdf_filename(chunk) -> str:
    """Extract base PDF filename from chunk metadata."""
    if chunk.file_ref:
        return chunk.file_ref
    if chunk.file and chunk.file.endswith(".pdf"):
        return Path(chunk.file).name
    if chunk.source_id and chunk.source_id.startswith(("pdf:", "poison:")):
        suffix = chunk.source_id.split(":", 1)[1]
        if suffix.endswith(".pdf"):
            return Path(suffix).name
    return f"{chunk.file}.pdf" if chunk.file else "document.pdf"


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/{chunk_id}/view", response_model=SourceViewResponse)
def get_source_view(
    chunk_id: str,
    hl: str | None = Query(None, description="Comma-separated start-end highlight offsets into chunk text"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourceViewResponse:
    """
    Retrieve structured source viewer data for a single chunk.
    Enforces ACL through SecureStore. Returns identical 404 for forbidden and nonexistent chunks.
    """
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    principal = build_principal(current_user)

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
            "endpoint": "source_view",
            "found": chunk is not None,
        },
    )

    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    spans = _parse_highlight_param(hl)
    clean_file = Path(chunk.file).name if chunk.file else "document"

    # 1. DB Row chunk
    if chunk.kind == "db_row" or chunk.row_id or (chunk.source_id and chunk.source_id.startswith("db:")):
        return SourceViewResponse(
            kind="db_row",
            file=clean_file,
            page=None,
            row_id=chunk.row_id,
            page_width=None,
            page_height=None,
            rects=[],
            match="none",
            text=chunk.text,
            page_image_url=None,
        )

    # 2. Image chunk
    if chunk.kind == "image" or (chunk.source_id and chunk.source_id.startswith("img:")):
        rects: list[RectOut] = []
        matched_box_count = 0

        if chunk.boxes and spans:
            # Match boxes overlapping highlight spans
            pos = 0
            for b in chunk.boxes:
                b_text = str(b.get("text", ""))
                b_s = pos
                b_e = pos + len(b_text)
                pos = b_e + 1  # space between line tokens
                for hs, he in spans:
                    if max(b_s, hs) < min(b_e, he):
                        rects.append(
                            RectOut(
                                x=round(float(b.get("x", 0.0)), 4),
                                y=round(float(b.get("y", 0.0)), 4),
                                w=round(float(b.get("w", 0.0)), 4),
                                h=round(float(b.get("h", 0.0)), 4),
                            )
                        )
                        matched_box_count += 1
                        break

        match_status: Literal["exact", "partial", "none"]
        if not spans or not rects:
            match_status = "none" if not spans else "partial"
        elif matched_box_count >= len(spans):
            match_status = "exact"
        else:
            match_status = "partial"

        pw = float(chunk.image_width) if chunk.image_width else None
        ph = float(chunk.image_height) if chunk.image_height else None
        page_image_url = f"/source/{quote(chunk.chunk_id, safe='')}/page.png"

        return SourceViewResponse(
            kind="image",
            file=clean_file,
            page=1,
            row_id=None,
            page_width=pw,
            page_height=ph,
            rects=rects,
            match=match_status,
            text=chunk.text,
            page_image_url=page_image_url,
        )

    # 3. Text / Markdown chunk
    if chunk.kind == "text" or (chunk.file and chunk.file.endswith((".txt", ".md"))):
        return SourceViewResponse(
            kind="text",
            file=clean_file,
            page=1,
            row_id=None,
            page_width=None,
            page_height=None,
            rects=[],
            match="none",
            text=chunk.text,
            page_image_url=None,
        )

    # 4. PDF chunk (pdf_text)
    try:
        pdf_name = _resolve_pdf_filename(chunk)
        pdf_path = asset_store.resolve_asset_path(pdf_name)
    except Exception as e:
        logger.warning(f"Could not resolve PDF file for chunk {chunk_id}: {e}")
        return SourceViewResponse(
            kind="pdf_text",
            file=clean_file,
            page=chunk.page,
            row_id=None,
            page_width=None,
            page_height=None,
            rects=[],
            match="none",
            text=chunk.text,
            page_image_url=None,
        )

    page_num = chunk.page if isinstance(chunk.page, int) else 1
    rects_raw, match_status_raw, pw, ph = compute_pdf_highlight_rects(
        pdf_path=pdf_path,
        page_num=page_num,
        chunk_text=chunk.text,
        highlight_spans=spans,
    )
    rects = [RectOut(**r) for r in rects_raw]
    match_status = match_status_raw if match_status_raw in ("exact", "partial", "none") else "none"  # type: ignore[assignment]
    page_image_url = f"/source/{quote(chunk.chunk_id, safe='')}/page.png?page={page_num}"

    return SourceViewResponse(
        kind="pdf_text",
        file=clean_file,
        page=page_num,
        row_id=None,
        page_width=pw,
        page_height=ph,
        rects=rects,
        match=match_status,  # type: ignore[arg-type]
        text=chunk.text,
        page_image_url=page_image_url,
    )


@router.get("/{chunk_id}/page.png")
def get_source_page_image(
    chunk_id: str,
    page: int | None = Query(None, ge=1, description="Page number override for PDF document"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """
    Serve rendered PNG page for a PDF or original image bytes for an image chunk.
    Enforces ACL through SecureStore:
      - forbidden chunks or unreadable pages return identical 404s.
      - db_row chunks return 404 (no page image).
    """
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    principal = build_principal(current_user)

    store = SecureStore()
    chunk = store.get_chunk(principal=principal, chunk_id=chunk_id)

    # 1. Non-existent or forbidden chunk
    if chunk is None or chunk.kind == "db_row" or chunk.row_id or (chunk.source_id and chunk.source_id.startswith("db:")):
        latency_ms = round((time.time() - t0) * 1000, 2)
        write_audit(
            db,
            user_id=user_id_str,
            event="citation",
            event_type="citation",
            refused=True,
            reason_code="not_found_or_forbidden",
            latency_ms=latency_ms,
            chunk_count=0,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "endpoint": "source_page_image"},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    # 2. Image chunk
    if chunk.kind == "image" or (chunk.source_id and chunk.source_id.startswith("img:")):
        if page is not None and page != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_NOT_FOUND["detail"],
            )
        try:
            target_ref = chunk.file_ref or chunk.file or chunk.chunk_id.removeprefix("img:").split("#")[0]
            content, mime = asset_store.get_asset(target_ref)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_NOT_FOUND["detail"],
            )

        latency_ms = round((time.time() - t0) * 1000, 2)
        write_audit(
            db,
            user_id=user_id_str,
            event="citation",
            event_type="citation",
            refused=False,
            reason_code="PAGE_IMAGE_SERVED",
            latency_ms=latency_ms,
            chunk_count=1,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "endpoint": "source_page_image", "kind": "image"},
        )
        return Response(
            content=content,
            media_type=mime,
            headers={"Cache-Control": "private, max-age=300"},
        )

    # 3. PDF chunk
    target_page = page if page is not None else (chunk.page if isinstance(chunk.page, int) else 1)
    readable_pages = store.get_readable_pages(principal=principal, source_id=chunk.source_id)

    if target_page not in readable_pages:
        latency_ms = round((time.time() - t0) * 1000, 2)
        write_audit(
            db,
            user_id=user_id_str,
            event="citation",
            event_type="citation",
            refused=True,
            reason_code="page_not_readable",
            latency_ms=latency_ms,
            chunk_count=0,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "page": target_page, "endpoint": "source_page_image"},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    try:
        pdf_name = _resolve_pdf_filename(chunk)
        pdf_path = asset_store.resolve_asset_path(pdf_name)
        png_bytes = render_pdf_page(pdf_path, target_page, dpi=150)
    except Exception as e:
        logger.warning(f"Error rendering PDF page {target_page} for {chunk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    latency_ms = round((time.time() - t0) * 1000, 2)
    write_audit(
        db,
        user_id=user_id_str,
        event="citation",
        event_type="citation",
        refused=False,
        reason_code="PAGE_IMAGE_SERVED",
        latency_ms=latency_ms,
        chunk_count=1,
        admin_access=is_admin,
        details={"chunk_id": chunk_id, "page": target_page, "endpoint": "source_page_image", "kind": "pdf"},
    )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{chunk_id}/pages", response_model=SourcePagesResponse)
def get_source_pages(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SourcePagesResponse:
    """
    Return total page count and readable pages list for a chunk's parent document.
    Enforces ACL through SecureStore:
      - forbidden chunks return 404.
      - readable_pages only includes pages where principal can read at least 1 chunk.
    """
    t0 = time.time()
    user_id_str = str(current_user.id)
    is_admin = ("admin" in (getattr(current_user, "roles", None) or [])) or (user_id_str == "u_admin")
    principal = build_principal(current_user)

    store = SecureStore()
    chunk = store.get_chunk(principal=principal, chunk_id=chunk_id)

    if chunk is None or chunk.kind == "db_row" or chunk.row_id or (chunk.source_id and chunk.source_id.startswith("db:")):
        latency_ms = round((time.time() - t0) * 1000, 2)
        write_audit(
            db,
            user_id=user_id_str,
            event="citation",
            event_type="citation",
            refused=True,
            reason_code="not_found_or_forbidden",
            latency_ms=latency_ms,
            chunk_count=0,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "endpoint": "source_pages"},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND["detail"],
        )

    # 1. Image
    if chunk.kind == "image" or (chunk.source_id and chunk.source_id.startswith("img:")):
        latency_ms = round((time.time() - t0) * 1000, 2)
        write_audit(
            db,
            user_id=user_id_str,
            event="citation",
            event_type="citation",
            refused=False,
            reason_code="SOURCE_PAGES_LISTED",
            latency_ms=latency_ms,
            chunk_count=1,
            admin_access=is_admin,
            details={"chunk_id": chunk_id, "endpoint": "source_pages", "kind": "image"},
        )
        return SourcePagesResponse(page_count=1, readable_pages=[1])

    # 2. PDF
    try:
        pdf_name = _resolve_pdf_filename(chunk)
        pdf_path = asset_store.resolve_asset_path(pdf_name)
        page_count = get_pdf_page_count(pdf_path)
    except Exception as e:
        logger.warning(f"Error reading PDF page count for {chunk_id}: {e}")
        page_count = chunk.page if isinstance(chunk.page, int) else 1

    readable_pages = store.get_readable_pages(principal=principal, source_id=chunk.source_id)

    latency_ms = round((time.time() - t0) * 1000, 2)
    write_audit(
        db,
        user_id=user_id_str,
        event="citation",
        event_type="citation",
        refused=False,
        reason_code="SOURCE_PAGES_LISTED",
        latency_ms=latency_ms,
        chunk_count=len(readable_pages),
        admin_access=is_admin,
        details={"chunk_id": chunk_id, "endpoint": "source_pages", "kind": "pdf"},
    )

    return SourcePagesResponse(
        page_count=page_count,
        readable_pages=readable_pages,
    )
