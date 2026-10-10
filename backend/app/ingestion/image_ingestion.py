"""
Image Ingestion Pipeline for VaultRAG.
Handles preprocessing, OCR, reading-order chunking, embedding, and idempotent upsert into Qdrant.
Access control tokens are strictly enforced and finalized. Sensitive text is never logged.
"""

from io import BytesIO
from pathlib import Path
import time
from typing import Any
from PIL import Image

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.schema import Chunk
from app.index.store import SecureStore
from app.ingestion.acl_policy import get_document_acl, load_acl_policy
from app.ocr.chunking import chunk_ocr_lines
from app.ocr.engine import ocr_image
from app.security.principals import doc_tokens, finalize_acl_tokens


def ingest_image(
    file_bytes_or_path: str | Path | bytes,
    source_id: str,
    acl_tokens: list[str] | set[str] | None = None,
    uploaded_by: str | None = None,
    corpus: str = "main",
    store: SecureStore | None = None,
    collection: str | None = None,
    db: Any = None,
) -> dict[str, Any]:
    """
    Ingest a single image file into Qdrant:
      1. Preprocess and perform OCR (RapidOCR)
      2. Chunk OCR lines into reading-order blocks with normalized bounding boxes
      3. Compute dense and sparse vector embeddings
      4. Idempotently upsert into Qdrant (deterministic point IDs from uuid5)
      5. Record audit row
    """
    t0 = time.time()
    store = store or SecureStore()
    coll = collection or settings.QDRANT_COLLECTION

    # Resolve filename and file_ref
    if isinstance(file_bytes_or_path, (str, Path)):
        p = Path(file_bytes_or_path)
        filename = p.name
        file_ref = f"images/{filename}"
    else:
        # Raw bytes: derive filename from source_id
        clean_name = source_id.removeprefix("img:")
        filename = clean_name if clean_name else "image.png"
        file_ref = f"images/{filename}"

    # Ensure ACL tokens are valid and finalized
    if acl_tokens is None:
        acl_policy = load_acl_policy()
        acl_info = get_document_acl(source_id, acl_policy)
        if not acl_info:
            raise ValueError(f"No ACL defined for {source_id} (fail-closed)")
        base_tokens = doc_tokens(acl_info)
    else:
        base_tokens = set(acl_tokens)

    if not base_tokens:
        raise ValueError(f"Empty ACL tokens for {source_id} (fail-closed)")

    tokens = finalize_acl_tokens(base_tokens)

    # 1. Preprocess & OCR
    lines, processed_img, ocr_meta = ocr_image(file_bytes_or_path)
    orig_w, orig_h = ocr_meta.get("orig_size", processed_img.size)

    # 2. Chunking (using original image dimensions)
    chunk_dicts = chunk_ocr_lines(
        lines=lines,
        filename=filename,
        img_width=orig_w,
        img_height=orig_h,
        file_ref=file_ref,
        max_chunk_chars=800,
    )

    if not chunk_dicts:
        # Fallback if image has no readable text
        chunk_dicts = [{
            "chunk_id": f"{source_id}#0",
            "source_id": source_id,
            "file": filename,
            "page": None,
            "kind": "image",
            "corpus": corpus,
            "text": "[Image contains no readable text]",
            "ocr_confidence": 0.0,
            "boxes": [],
            "image_width": orig_w,
            "image_height": orig_h,
            "file_ref": file_ref,
        }]

    # 3. Build Chunk models
    chunks: list[Chunk] = []
    for cd in chunk_dicts:
        c = Chunk(
            chunk_id=cd["chunk_id"],
            doc_id=source_id,
            source_doc=filename,
            source_id=source_id,
            source_type="image",
            source_name=Path(filename).stem,
            corpus=corpus,  # type: ignore[arg-type]
            page=None,
            file=filename,
            kind="image",
            text=cd["text"],
            ocr_confidence=cd.get("ocr_confidence", 0.0),
            boxes=cd.get("boxes", []),
            image_width=cd.get("image_width", orig_w),
            image_height=cd.get("image_height", orig_h),
            file_ref=cd.get("file_ref", file_ref),
            owner_id=uploaded_by or "u_admin",
            acl_tokens=tokens,
            classification_label="internal",
        )
        chunks.append(c)

    # 4. Idempotent Upsert: delete previous points for doc_id, then upsert
    store.delete_by_doc(source_id, collection=coll)

    embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()
    texts = [c.text for c in chunks]
    dense_vecs = embedder.embed(texts)
    sparse_vecs = sparse_embedder.embed_sparse(texts)

    store.upsert_chunks(chunks, dense_vecs, sparse_vecs, collection=coll)

    # 5. Audit Logging (IDs and metadata only, no OCR text)
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        user_ext = uploaded_by or "u_admin"
        admin_user = db.query(User).filter(User.external_id == user_ext).first()
        user_uuid = admin_user.id if admin_user else user_ext

        write_audit(
            db=db,
            user_id=str(user_uuid),
            event="ingest_image",
            event_type="ingest_image",
            refused=False,
            reason_code="IMAGE_INGESTED",
            chunk_count=len(chunks),
            details={"source_id": source_id, "file_name": filename},
        )
    finally:
        if own_db:
            db.close()

    elapsed = round(time.time() - t0, 3)
    mean_conf = round(sum(l.confidence for l in lines) / len(lines), 3) if lines else 0.0

    return {
        "source_id": source_id,
        "file_name": filename,
        "total_chunks": len(chunks),
        "ocr_lines": len(lines),
        "mean_confidence": mean_conf,
        "elapsed_seconds": elapsed,
        "acl_tokens": tokens,
    }


def ingest_images_corpus(
    store: SecureStore | None = None,
    collection: str | None = None,
    image_dir: Path | str | None = None,
    only: str | None = None,
    corpus: str = "main",
) -> list[dict[str, Any]]:
    """
    Ingest all corpus images from dataset into Qdrant.
    """
    store = store or SecureStore()
    coll = collection or settings.QDRANT_COLLECTION

    if image_dir is not None:
        img_dir_path = Path(image_dir)
    else:
        ds_path = settings.dataset_path()
        candidates = [
            ds_path / "dataset" / "corpus" / "images",
            ds_path / "corpus" / "images",
        ]
        img_dir_path = next((c for c in candidates if c.is_dir()), candidates[0])

    if not img_dir_path.is_dir():
        raise FileNotFoundError(f"Image corpus directory not found at: {img_dir_path}")

    acl_policy = load_acl_policy()
    results: list[dict[str, Any]] = []

    # Find image files
    all_files = sorted(
        [p for p in img_dir_path.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    )

    for p in all_files:
        if only and p.name != only and f"img:{p.name}" != only:
            continue

        source_id = f"img:{p.name}"
        acl_info = get_document_acl(source_id, acl_policy)
        if not acl_info:
            print(f"  [WARN] Skipping {p.name}: No ACL defined for {source_id}")
            continue

        base_tokens = doc_tokens(acl_info)
        res = ingest_image(
            file_bytes_or_path=p,
            source_id=source_id,
            acl_tokens=base_tokens,
            corpus=corpus,
            store=store,
            collection=coll,
        )
        results.append(res)

    return results
