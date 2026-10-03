"""
PDF ingestion pipeline: load, chunk, tag, delete old doc chunks, embed, upsert, and audit.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.ingestion.acl_tagger import tag_chunks
from app.ingestion.chunker import chunk_document, make_token_counter
from app.ingestion.manifest import load_manifest, resolve_manifest
from app.ingestion.pdf_loader import load_pdf

logger = logging.getLogger(__name__)


def derive_doc_id(file_path: str | Path) -> str:
    """Derive a stable doc_id slug from the filename (without extension)."""
    return Path(file_path).stem.strip().lower().replace(" ", "_")


def ingest_pdf(
    path: str | Path,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db: Session | None = None,
    manifest: dict | None = None,
) -> dict:
    """
    Ingest a single PDF file into the vector store with ACL tagging.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    doc_id = derive_doc_id(pdf_path)
    store = store or SecureStore()
    embedder = embedder or DenseEmbedder()
    sparse = sparse or SparseEmbedder()

    # Manage DB session if not provided
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        if manifest is None:
            manifest = load_manifest()

        # 1. Load PDF text and tables
        doc_data = load_pdf(pdf_path)

        # 2. Chunk document per page
        token_counter = make_token_counter(embedder)
        raw_chunks = chunk_document(doc_data["pages"], doc_id, token_counter=token_counter)

        # 3. Resolve ACL from manifest and DB
        acl_info = resolve_manifest(db, manifest, pdf_path.name)

        # 4. Tag chunks with ACL and validate schema (fails closed on invalid data)
        chunks = tag_chunks(raw_chunks, acl_info, source_name=pdf_path.name, source_type="pdf")

        # 5. Delete previous chunks for this document (prevents stale chunks on re-ingest)
        store.delete_by_doc(doc_id, collection=collection)

        # 6. Embed and upsert if any chunks exist
        if chunks:
            texts = [c.text for c in chunks]
            dense_vectors = embedder.embed(texts)
            sparse_vectors = sparse.embed_sparse(texts)
            store.upsert_chunks(chunks, dense_vectors, sparse_vectors, collection=collection)

        # 7. Audit log entry
        write_audit(
            db,
            user_id=acl_info["owner_id"],
            event="ingest",
            details={
                "file": pdf_path.name,
                "doc_id": doc_id,
                "chunks": len(chunks),
                "acl": {
                    "allowed_roles": acl_info["allowed_roles"],
                    "classification": acl_info["classification"],
                    "is_public": acl_info["is_public"],
                },
            },
        )

        text_chunk_count = sum(1 for c in chunks if c.chunk_type == "text")
        table_chunk_count = sum(1 for c in chunks if c.chunk_type == "table")

        return {
            "doc_id": doc_id,
            "file_name": pdf_path.name,
            "pages": doc_data["total_pages"],
            "text_chunks": text_chunk_count,
            "table_chunks": table_chunk_count,
            "total_chunks": len(chunks),
            "empty_pages": doc_data["empty_pages"],
            "allowed_roles": acl_info["allowed_roles"],
            "classification": acl_info["classification"],
        }
    finally:
        if own_db:
            db.close()


def ingest_folder(
    folder_path: str | Path,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db: Session | None = None,
    manifest_path: str | Path | None = None,
) -> list[dict]:
    """
    Ingest all PDFs in a folder.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"Directory not found: {folder}")

    manifest_p = Path(manifest_path) if manifest_path else None
    manifest = load_manifest(manifest_p)

    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    results = []
    try:
        pdf_files = sorted(folder.glob("*.pdf"))
        for pdf_file in pdf_files:
            summary = ingest_pdf(
                path=pdf_file,
                store=store,
                embedder=embedder,
                sparse=sparse,
                collection=collection,
                db=db,
                manifest=manifest,
            )
            results.append(summary)
        return results
    finally:
        if own_db:
            db.close()
