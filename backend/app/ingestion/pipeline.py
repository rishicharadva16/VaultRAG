"""
Dataset ingestion pipeline: load, chunk, permission tag, delete old doc chunks,
embed, upsert to SecureStore, and record audit log.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.schema import Chunk
from app.index.store import SecureStore
from app.ingestion.acl_policy import get_document_acl, load_acl_policy, resolve_source_id
from app.ingestion.chunker import chunk_document, make_token_counter
from app.ingestion.db_ingestion import ingest_database, load_db_chunks
from app.ingestion.html_loader import load_html
from app.ingestion.md_loader import load_md
from app.ingestion.pdf_loader import load_pdf
from app.security.principals import doc_tokens, finalize_acl_tokens

logger = logging.getLogger(__name__)


def derive_doc_id(file_path: str | Path) -> str:
    """Derive a stable doc_id slug from the filename (without extension)."""
    return Path(file_path).stem.strip().lower().replace(" ", "_")


def ingest_document(
    path: str | Path,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db: Session | None = None,
    corpus: str = "main",
    acl_policy_map: dict | None = None,
) -> dict:
    """
    Ingest a single document (PDF, Markdown, or HTML) into Qdrant with ACL tokens.
    Fail-closed: unlisted documents or documents resulting in empty permission tokens are rejected.
    """
    doc_path = Path(path)
    if not doc_path.exists():
        raise FileNotFoundError(f"File not found: {doc_path}")

    ext = doc_path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg"):
        raise NotImplementedError(f"Skipping {doc_path.name}: images pending Step 4 (OCR)")

    doc_id = derive_doc_id(doc_path)
    store = store or SecureStore()
    embedder = embedder or DenseEmbedder()
    sparse = sparse or SparseEmbedder()

    # Determine source_id and corpus
    is_poison = doc_path.parent.name == "poisoned" or doc_path.name.startswith("poison_")
    if is_poison:
        corpus = "poison_test"
        source_id = f"poison:{doc_path.name}"
    else:
        source_id = resolve_source_id(doc_path.name)

    if acl_policy_map is None:
        acl_policy_map = load_acl_policy()

    acl_info = get_document_acl(source_id, acl_policy_map)
    if acl_info is None:
        raise ValueError(f"No ACL defined for {source_id} in acl_policy.json (fail-closed)")

    base_tokens = doc_tokens(acl_info)
    if not base_tokens:
        raise ValueError(f"Empty permission tokens for {source_id} (fail-closed)")
    tokens = finalize_acl_tokens(base_tokens)

    # 1. Load document content
    if ext == ".pdf":
        doc_data = load_pdf(doc_path)
        source_type = "pdf"
    elif ext == ".md":
        doc_data = load_md(doc_path)
        source_type = "md"
    elif ext in (".html", ".htm"):
        doc_data = load_html(doc_path)
        source_type = "html"
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    # 2. Chunk document
    token_counter = make_token_counter(embedder)
    raw_chunks = chunk_document(doc_data["pages"], doc_id, token_counter=token_counter)

    # 3. Create Chunk models
    chunks: list[Chunk] = []
    for raw in raw_chunks:
        c = Chunk(
            chunk_id=raw["chunk_id"],
            doc_id=doc_id,
            source_doc=doc_path.name,
            source_id=source_id,
            source_type=source_type,
            source_name=doc_path.stem,
            corpus=corpus,
            page=raw.get("page"),
            bbox=raw.get("bbox"),
            table=raw.get("table"),
            row_pk=raw.get("row_pk"),
            chunk_type=raw.get("chunk_type", "text"),
            text=raw["text"],
            owner_id="u_admin",
            allowed_roles=acl_info.get("allowed_roles", []),
            allowed_employees=acl_info.get("allowed_employees", []),
            allowed_departments=acl_info.get("allowed_departments", []),
            acl_tokens=tokens,
            classification_label=acl_info.get("classification", "internal"),
        )
        chunks.append(c)

    # 4. Delete previous chunks for this doc_id
    store.delete_by_doc(doc_id, collection=collection)

    # 5. Embed and upsert
    if chunks:
        texts = [c.text for c in chunks]
        dense_vectors = embedder.embed(texts)
        sparse_vectors = sparse.embed_sparse(texts)
        store.upsert_chunks(chunks, dense_vectors, sparse_vectors, collection=collection)

    # 6. Audit log entry
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        admin_user = db.query(User).filter(User.external_id == "u_admin").first()
        admin_id = admin_user.id if admin_user else "u_admin"

        write_audit(
            db,
            user_id=admin_id,
            event="ingest",
            details={
                "file": doc_path.name,
                "source_id": source_id,
                "doc_id": doc_id,
                "corpus": corpus,
                "chunks": len(chunks),
                "acl_tokens": tokens,
            },
        )
    except Exception as e:
        logger.warning("Failed to record audit log for %s: %s", doc_path.name, e)
    finally:
        if own_db:
            db.close()

    text_count = sum(1 for c in chunks if c.chunk_type == "text")
    table_count = sum(1 for c in chunks if c.chunk_type == "table")

    return {
        "doc_id": doc_id,
        "source_id": source_id,
        "file_name": doc_path.name,
        "corpus": corpus,
        "pages": doc_data["total_pages"],
        "text_chunks": text_count,
        "table_chunks": table_count,
        "total_chunks": len(chunks),
        "empty_pages": doc_data["empty_pages"],
        "acl_tokens": tokens,
    }


def ingest_pdf(
    path: str | Path,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db: Session | None = None,
    corpus: str = "main",
    acl_policy_map: dict | None = None,
    manifest: dict | None = None,
) -> dict:
    """Backward-compatible wrapper for PDF ingestion."""
    return ingest_document(
        path=path,
        store=store,
        embedder=embedder,
        sparse=sparse,
        collection=collection,
        db=db,
        corpus=corpus,
        acl_policy_map=acl_policy_map,
    )


def find_corpus_dir(root: str | Path | None = None) -> Path:
    """Locate the corpus directory containing pdfs and poisoned subfolders."""
    if root:
        p = Path(root)
        if p.exists():
            return p

    ds_path = settings.dataset_path()
    candidates = [
        ds_path / "dataset" / "corpus",
        ds_path / "corpus",
    ]
    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(f"Corpus directory not found under {ds_path}")


def ingest_corpus(
    root: str | Path | None = None,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db: Session | None = None,
    include_poison: bool = False,
    only: str | None = None,
) -> list[dict]:
    """
    Ingest the dataset corpus:
    - 7 main PDFs under corpus/pdfs
    - optionally 3 poison files under corpus/poisoned
    Images are skipped (pending OCR in Step 4).
    """
    corpus_dir = find_corpus_dir(root)
    acl_map = load_acl_policy()

    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    results = []
    try:
        # 1. Main PDFs
        pdfs_dir = corpus_dir / "pdfs"
        if pdfs_dir.exists():
            for pdf_file in sorted(pdfs_dir.glob("*.pdf")):
                if only and pdf_file.name != only and pdf_file.stem != only:
                    continue
                summary = ingest_document(
                    path=pdf_file,
                    store=store,
                    embedder=embedder,
                    sparse=sparse,
                    collection=collection,
                    db=db,
                    corpus="main",
                    acl_policy_map=acl_map,
                )
                results.append(summary)

        # 2. Poison files (optional)
        if include_poison:
            poison_dir = corpus_dir / "poisoned"
            if poison_dir.exists():
                for poison_file in sorted(poison_dir.iterdir()):
                    if poison_file.suffix.lower() == ".json":
                        continue
                    if only and poison_file.name != only and poison_file.stem != only:
                        continue
                    summary = ingest_document(
                        path=poison_file,
                        store=store,
                        embedder=embedder,
                        sparse=sparse,
                        collection=collection,
                        db=db,
                        corpus="poison_test",
                        acl_policy_map=acl_map,
                    )
                    results.append(summary)

        return results
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
    corpus: str = "main",
    manifest_path: str | Path | None = None,
) -> list[dict]:
    """Ingest all supported documents in a folder."""
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"Directory not found: {folder}")
    acl_map = load_acl_policy()
    results = []
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in (".pdf", ".md", ".html", ".htm"):
            res = ingest_document(
                path=f,
                store=store,
                embedder=embedder,
                sparse=sparse,
                collection=collection,
                db=db,
                corpus=corpus,
                acl_policy_map=acl_map,
            )
            results.append(res)
    return results

