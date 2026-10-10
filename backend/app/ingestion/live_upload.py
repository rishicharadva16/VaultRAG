"""
Live Upload Ingestion Pipeline and Background Worker.
Handles magic byte validation, deduplication, parsing (PDF, image, CSV, text),
prompt-injection flagging, single-job background execution, and in-place ACL updates.
Sensitive document text and tokens are NEVER logged.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
from pathlib import Path
import re
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import Document, DocumentShare, User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.schema import Chunk
from app.index.store import SecureStore
from app.ingestion.chunker import chunk_document, make_token_counter
from app.ingestion.pdf_loader import load_pdf
from app.ocr.chunking import chunk_ocr_lines
from app.ocr.engine import ocr_image
from app.rag.answer import CANARY, POISON_CANARIES
from app.security.principals import finalize_acl_tokens

logger = logging.getLogger(__name__)

# Prompt injection regex patterns
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"reply\s+pwned", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
]


def detect_file_type(content: bytes, filename_hint: str = "") -> tuple[str, str]:
    """
    Decide kind (pdf | image | csv | text) and canonical extension
    by magic bytes, not client-supplied content type.
    Raises ValueError('unsupported_media_type') on mismatch or unsupported format.
    """
    if not content:
        raise ValueError("empty_file")

    # 1. PDF: %PDF
    if content.startswith(b"%PDF"):
        return "pdf", ".pdf"

    # 2. PNG: \x89PNG\r\n\x1a\n
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", ".png"

    # 3. JPEG: \xff\xd8\xff
    if content.startswith(b"\xff\xd8\xff"):
        return "image", ".jpg"

    # 4. Text-based files (CSV, Markdown, Plain Text)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise ValueError("unsupported_media_type")

    # Check for binary null bytes
    if "\x00" in text:
        raise ValueError("unsupported_media_type")

    lower_hint = filename_hint.lower()
    
    # Check if CSV
    is_csv = False
    if lower_hint.endswith(".csv"):
        is_csv = True
    else:
        # Sniff for CSV delimiters across multiple lines
        lines = [line.strip() for line in text.splitlines() if line.strip()][:5]
        if len(lines) >= 1 and all("," in line for line in lines):
            is_csv = True

    if is_csv:
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if rows and len(rows[0]) >= 1:
                return "csv", ".csv"
        except Exception:
            pass

    # Markdown vs Plain text
    if lower_hint.endswith(".md"):
        return "text", ".md"

    return "text", ".txt"


def sanitize_filename(filename: str) -> str:
    """Sanitize display filename, keeping only safe characters."""
    base = Path(filename).name
    cleaned = re.sub(r"[^\w\s.-]", "_", base).strip()
    return cleaned or "document"


def is_prompt_injection(text: str) -> bool:
    """Detect presence of prompt injection markers in ingested text."""
    if CANARY in text:
        return True
    for pc in POISON_CANARIES:
        if pc in text:
            return True
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return False


def compute_document_tokens(doc: Document, shares: list[DocumentShare]) -> list[str]:
    """Compute canonical ACL tokens for base chunks of a document."""
    tokens = {f"usr:{doc.owner_id}"}
    for s in shares:
        if s.grantee_type == "user":
            tokens.add(f"usr:{s.grantee_value}")
        elif s.grantee_type == "role":
            tokens.add(f"role:{s.grantee_value}")
        elif s.grantee_type == "department":
            tokens.add(f"dept:{s.grantee_value}")
    return finalize_acl_tokens(tokens)


def compute_sensitive_tokens(doc: Document, shares: list[DocumentShare]) -> list[str]:
    """Compute canonical ACL tokens for sensitive CSV chunks."""
    tokens = {f"usr:{doc.owner_id}"}
    for s in shares:
        if s.include_sensitive:
            if s.grantee_type == "user":
                tokens.add(f"usr:{s.grantee_value}")
            elif s.grantee_type == "role":
                tokens.add(f"role:{s.grantee_value}")
            elif s.grantee_type == "department":
                tokens.add(f"dept:{s.grantee_value}")
    return finalize_acl_tokens(tokens)


# ── Ingestion Worker ──────────────────────────────────────────

_upload_queue: asyncio.Queue[str] | None = None
_worker_task: asyncio.Task | None = None


def get_upload_queue() -> asyncio.Queue[str]:
    global _upload_queue
    if _upload_queue is None:
        _upload_queue = asyncio.Queue()
    return _upload_queue


async def start_upload_worker():
    """Start the single sequential background ingestion worker."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_upload_worker_loop())


async def _upload_worker_loop():
    """Worker loop pulling one document ID at a time."""
    q = get_upload_queue()
    while True:
        try:
            doc_id = await q.get()
            try:
                # Run CPU/GPU heavy ingestion in default threadpool
                await asyncio.to_thread(process_document, doc_id)
            except Exception as e:
                logger.exception("Failed background ingestion for doc %s: %s", doc_id, e)
            finally:
                q.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in upload worker loop: %s", e)
            await asyncio.sleep(1.0)


def process_document(document_id: str, db: Session | None = None) -> bool:
    """
    Process ingestion for a single document synchronously.
    Transitions: queued -> processing -> ready | failed
    """
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        doc: Document | None = db.query(Document).filter(Document.id == document_id).first()
        if not doc or doc.deleted_at is not None:
            return False

        if doc.status == "ready":
            return True

        # Transition to processing
        doc.status = "processing"
        doc.reason_code = None
        db.commit()

        storage_root = settings.storage_path()
        doc_dir = storage_root / "uploads" / doc.id
        
        # Locate original file in doc_dir
        matching_files = list(doc_dir.glob("original.*"))
        if not matching_files:
            doc.status = "failed"
            doc.reason_code = "file_missing"
            db.commit()
            return False

        orig_file = matching_files[0]
        ext = orig_file.suffix.lower()
        file_ref = f"uploads/{doc.id}/original{ext}"

        # Load shares
        shares = db.query(DocumentShare).filter(DocumentShare.document_id == doc.id).all()
        base_tokens = compute_document_tokens(doc, shares)
        sens_tokens = compute_sensitive_tokens(doc, shares)

        embedder = DenseEmbedder()
        sparse = SparseEmbedder()
        store = SecureStore()
        token_counter = make_token_counter(embedder)

        chunks: list[Chunk] = []

        if doc.kind == "pdf":
            doc_data = load_pdf(orig_file)
            raw_chunks = chunk_document(doc_data["pages"], doc_id=doc.source_id, token_counter=token_counter)
            for idx, raw in enumerate(raw_chunks):
                txt = raw["text"]
                flagged = is_prompt_injection(txt)
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.source_id}#{idx}",
                        doc_id=doc.source_id,
                        source_doc=doc.filename,
                        source_id=doc.source_id,
                        source_type="pdf",
                        source_name=Path(doc.filename).stem,
                        corpus="main",
                        file=doc.filename,
                        page=raw.get("page", 1),
                        kind="pdf_text",
                        text=txt,
                        file_ref=file_ref,
                        owner_id=doc.owner_id,
                        acl_tokens=base_tokens,
                        flagged=flagged,
                    )
                )

        elif doc.kind == "image":
            file_bytes = orig_file.read_bytes()
            lines, processed_img, ocr_meta = ocr_image(file_bytes)
            orig_w, orig_h = ocr_meta.get("orig_size", processed_img.size)
            chunk_dicts = chunk_ocr_lines(
                lines=lines,
                filename=doc.filename,
                img_width=orig_w,
                img_height=orig_h,
                file_ref=file_ref,
                max_chunk_chars=800,
            )
            if not chunk_dicts:
                chunk_dicts = [{
                    "chunk_id": f"{doc.source_id}#0",
                    "text": "[Image contains no readable text]",
                    "ocr_confidence": 0.0,
                    "boxes": [],
                }]

            for idx, cd in enumerate(chunk_dicts):
                txt = cd["text"]
                flagged = is_prompt_injection(txt)
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.source_id}#{idx}",
                        doc_id=doc.source_id,
                        source_doc=doc.filename,
                        source_id=doc.source_id,
                        source_type="image",
                        source_name=Path(doc.filename).stem,
                        corpus="main",
                        file=doc.filename,
                        page=None,
                        kind="image",
                        text=txt,
                        ocr_confidence=cd.get("ocr_confidence", 0.0),
                        boxes=cd.get("boxes", []),
                        image_width=orig_w,
                        image_height=orig_h,
                        file_ref=file_ref,
                        owner_id=doc.owner_id,
                        acl_tokens=base_tokens,
                        flagged=flagged,
                    )
                )

        elif doc.kind == "csv":
            text = orig_file.read_text(encoding="utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            sens_cols = set(doc.sensitive_columns or [])

            for r_idx, row in enumerate(reader, 1):
                base_items = [(k, v) for k, v in row.items() if k not in sens_cols]
                sens_items = [(k, v) for k, v in row.items() if k in sens_cols]

                # Base chunk
                if base_items:
                    row_str = ", ".join(f"{k} {v}" for k, v in base_items)
                    base_text = f"Record {r_idx} ({doc.filename}): {row_str}."
                    flagged = is_prompt_injection(base_text)
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc.source_id}#{r_idx}:base",
                            doc_id=doc.source_id,
                            source_doc=doc.filename,
                            source_id=doc.source_id,
                            source_type="csv",
                            source_name=Path(doc.filename).stem,
                            corpus="main",
                            file=doc.filename,
                            table=doc.filename,
                            row_id=str(r_idx),
                            row_pk=str(r_idx),
                            kind="db_row",
                            text=base_text,
                            file_ref=file_ref,
                            owner_id=doc.owner_id,
                            acl_tokens=base_tokens,
                            flagged=flagged,
                            is_sensitive=False,
                        )
                    )

                # Sensitive chunk
                if sens_items:
                    sens_str = ", ".join(f"{k} {v}" for k, v in sens_items)
                    sens_text = f"Sensitive record {r_idx} ({doc.filename}): {sens_str}."
                    flagged = is_prompt_injection(sens_text)
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc.source_id}#{r_idx}:sensitive",
                            doc_id=doc.source_id,
                            source_doc=doc.filename,
                            source_id=doc.source_id,
                            source_type="csv",
                            source_name=Path(doc.filename).stem,
                            corpus="main",
                            file=doc.filename,
                            table=doc.filename,
                            row_id=str(r_idx),
                            row_pk=str(r_idx),
                            kind="db_row",
                            text=sens_text,
                            file_ref=file_ref,
                            owner_id=doc.owner_id,
                            acl_tokens=sens_tokens,
                            flagged=flagged,
                            is_sensitive=True,
                        )
                    )

        elif doc.kind == "text":
            text = orig_file.read_text(encoding="utf-8", errors="replace")
            pages = [{"page": 1, "text": text}]
            raw_chunks = chunk_document(pages, doc_id=doc.source_id, token_counter=token_counter)
            for idx, raw in enumerate(raw_chunks):
                txt = raw["text"]
                flagged = is_prompt_injection(txt)
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.source_id}#{idx}",
                        doc_id=doc.source_id,
                        source_doc=doc.filename,
                        source_id=doc.source_id,
                        source_type="text",
                        source_name=Path(doc.filename).stem,
                        corpus="main",
                        file=doc.filename,
                        page=1,
                        kind="text",
                        text=txt,
                        file_ref=file_ref,
                        owner_id=doc.owner_id,
                        acl_tokens=base_tokens,
                        flagged=flagged,
                    )
                )

        # Upsert chunks to Qdrant
        if chunks:
            store.delete_by_source_id(doc.source_id)
            texts = [c.text for c in chunks]
            dense_vectors = embedder.embed(texts)
            sparse_vectors = sparse.embed_sparse(texts)
            store.upsert_chunks(chunks, dense_vectors, sparse_vectors)

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        doc.reason_code = None
        db.commit()

        # Audit log
        write_audit(
            db,
            user_id=doc.owner_id,
            event="upload_ingest",
            event_type="upload_ingest",
            refused=False,
            reason_code="READY",
            chunk_count=len(chunks),
            details={
                "doc_id": doc.id,
                "source_id": doc.source_id,
                "kind": doc.kind,
                "chunks": len(chunks),
            },
        )
        return True

    except Exception as e:
        logger.exception("Ingestion failed for doc %s: %s", document_id, e)
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                doc.reason_code = "processing_error"
                db.commit()
        except Exception:
            pass
        return False
    finally:
        if own_db:
            db.close()
