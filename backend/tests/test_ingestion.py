"""
Tests for Step 2: chunk schema, ACL manifest, PDF ingestion, and SecureStore.
Uses QDRANT_TEST_COLLECTION and fake embedders for fast execution.
Includes a slow test for the real bge-m3 model.
"""

import json
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

from app.config import settings
from app.db.models import User
from app.index.embedder import DenseEmbedder, FakeDenseEmbedder, FakeSparseEmbedder
from app.index.schema import ROLES, Chunk, point_id
from app.index.store import SecureStore
from app.ingestion.acl_tagger import tag_chunks
from app.ingestion.chunker import chunk_document, estimate_tokens
from app.ingestion.manifest import load_manifest, resolve_manifest
from app.ingestion.pipeline import derive_doc_id, ingest_folder, ingest_pdf
from scripts.make_demo_pdfs import main as generate_demo_pdfs


@pytest.fixture(scope="module")
def ensure_demo_pdfs():
    """Ensure demo PDFs and facts exist before running tests."""
    pdf_dir = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"
    manifest_file = Path(__file__).resolve().parent.parent.parent / "data" / "acl_manifest.json"
    if not pdf_dir.exists() or len(list(pdf_dir.glob("*.pdf"))) < 6:
        generate_demo_pdfs()
    assert manifest_file.exists()


@pytest.fixture()
def test_collection():
    """Create and tear down a dedicated Qdrant test collection."""
    store = SecureStore()
    coll = settings.QDRANT_TEST_COLLECTION
    fake_dim = 8
    # Cleanup previous run if any
    try:
        store.delete_collection(coll)
    except Exception:
        pass

    store.ensure_collection(dense_size=fake_dim, collection=coll)
    yield coll

    try:
        store.delete_collection(coll)
    except Exception:
        pass


@pytest.fixture()
def ingested_collection(db, ensure_demo_pdfs, test_collection):
    """Ingest demo PDFs into the test collection."""
    store = SecureStore()
    fake_dense = FakeDenseEmbedder(size=8)
    fake_sparse = FakeSparseEmbedder()
    pdf_dir = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"

    ingest_folder(
        pdf_dir,
        store=store,
        embedder=fake_dense,
        sparse=fake_sparse,
        collection=test_collection,
        db=db,
    )
    return test_collection


# ── B2: Schema Validation Tests ───────────────────────────────────

def test_schema_rejects_invalid_classification():
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id=str(uuid.uuid4()), text="Valid text", classification=0,
        )
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id=str(uuid.uuid4()), text="Valid text", classification=4,
        )


def test_schema_rejects_unknown_role():
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id=str(uuid.uuid4()), text="Valid text", allowed_roles=["superuser"],
        )


def test_schema_rejects_empty_text():
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id=str(uuid.uuid4()), text="",
        )
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id=str(uuid.uuid4()), text="   \n  ",
        )


def test_schema_rejects_missing_owner():
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
            owner_id="", text="Valid text",
        )


def test_schema_admin_always_in_allowed_roles():
    owner = str(uuid.uuid4())
    chunk = Chunk(
        chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
        owner_id=owner, text="Valid text", allowed_roles=["hr"],
    )
    assert "admin" in chunk.allowed_roles
    assert "hr" in chunk.allowed_roles


def test_schema_defaults_to_admin_only_with_owner():
    owner = str(uuid.uuid4())
    chunk = Chunk(
        chunk_id="doc-p1-c1", doc_id="doc", source_type="pdf", source_name="doc.pdf",
        owner_id=owner, text="Valid text", allowed_roles=[], allowed_users=[], is_public=False,
    )
    assert chunk.allowed_roles == ["admin"]
    assert owner in chunk.allowed_users


# ── B3: Manifest Tests ───────────────────────────────────────────

def test_manifest_unknown_email_raises(db):
    manifest = {
        "test.pdf": {
            "owner_email": "nonexistent_owner@vaultrag.local",
            "allowed_roles": ["hr"],
            "allowed_user_emails": [],
            "classification": 1,
            "is_public": False,
        }
    }
    with pytest.raises(ValueError, match="nonexistent_owner@vaultrag.local"):
        resolve_manifest(db, manifest, "test.pdf")

    # Allowed user email not found
    admin = db.query(User).filter(User.roles.any("admin")).first()
    manifest_bad_user = {
        "test.pdf": {
            "owner_email": admin.email,
            "allowed_roles": ["hr"],
            "allowed_user_emails": ["missing_user@vaultrag.local"],
            "classification": 1,
            "is_public": False,
        }
    }
    with pytest.raises(ValueError, match="missing_user@vaultrag.local"):
        resolve_manifest(db, manifest_bad_user, "test.pdf")


def test_manifest_missing_file_becomes_admin_only(db):
    resolved = resolve_manifest(db, {}, "unlisted_file.pdf")
    assert resolved["allowed_roles"] == ["admin"]
    assert resolved["classification"] == 3
    assert resolved["is_public"] is False
    assert resolved["owner_id"] is not None


# ── B6: Chunker Tests ────────────────────────────────────────────

def test_chunker_never_crosses_pages_and_respects_token_limit():
    pages_data = [
        {"page": 1, "text": "Page one text. " * 30, "tables": []},
        {"page": 2, "text": "Page two text. " * 40, "tables": []},
    ]
    chunks = chunk_document(pages_data, "test_doc", token_counter=estimate_tokens)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["page"] in (1, 2)
        if c["page"] == 1:
            assert "Page one" in c["text"]
            assert "Page two" not in c["text"]
        elif c["page"] == 2:
            assert "Page two" in c["text"]
            assert "Page one" not in c["text"]
        assert estimate_tokens(c["text"]) <= 500


# ── B6 & B7: Ingestion & Verification Tests ───────────────────────

def test_board_minutes_fact_and_contract_table(ingested_collection):
    store = SecureStore()
    coll = ingested_collection

    # Check board minutes page 4 fact
    board_points = store.admin_scroll(limit=50, doc_id="board_minutes", collection=coll)
    p4_chunks = [p for p in board_points if p.payload.get("page") == 4]
    assert len(p4_chunks) >= 1
    found_fact = any(
        "The board approved a marketing budget of Rs. 12 lakh for Q3." in p.payload.get("text", "")
        for p in p4_chunks
    )
    assert found_fact, "Board minutes Q3 marketing budget fact not found on page 4!"

    # Check vendor contract has table chunk
    contract_points = store.admin_scroll(limit=50, doc_id="vendor_contract", collection=coll)
    table_chunks = [p for p in contract_points if p.payload.get("chunk_type") == "table"]
    assert len(table_chunks) >= 1, "Vendor contract must produce at least one table chunk!"
    assert any("Software licence" in p.payload.get("text", "") and "Rs. 2,40,000" in p.payload.get("text", "") for p in table_chunks)


def test_confidential_sentences_not_in_public_chunks(ingested_collection):
    store = SecureStore()
    all_points = store.admin_scroll(limit=200, collection=ingested_collection)
    public_points = [p for p in all_points if p.payload.get("is_public") is True]

    restricted_1 = "Executive leave encashment is capped at 45 days."
    restricted_2 = "Unused leave carry-forward is limited to 8 days."

    for p in public_points:
        text = p.payload.get("text", "")
        assert restricted_1 not in text, f"Confidential fact leaked in public chunk: {p.payload.get('chunk_id')}"
        assert restricted_2 not in text, f"Confidential fact leaked in public chunk: {p.payload.get('chunk_id')}"


def test_every_stored_point_has_complete_acl_and_valid_point_id(ingested_collection):
    store = SecureStore()
    points = store.admin_scroll(limit=200, collection=ingested_collection)
    assert len(points) > 0

    required_keys = {
        "chunk_id", "doc_id", "source_type", "source_name", "page",
        "chunk_type", "text", "allowed_roles", "allowed_users",
        "owner_id", "classification", "is_public", "deleted", "created_at",
    }

    for pt in points:
        payload = pt.payload
        # Check all required keys exist
        for k in required_keys:
            assert k in payload, f"Missing payload key {k} in chunk {pt.id}"

        # Check point id is deterministic uuid5 from chunk_id
        expected_pid = point_id(payload["chunk_id"])
        assert str(pt.id) == expected_pid


def test_idempotent_ingestion_leaves_point_count_unchanged(db, ensure_demo_pdfs, ingested_collection):
    store = SecureStore()
    fake_dense = FakeDenseEmbedder(size=8)
    fake_sparse = FakeSparseEmbedder()
    pdf_dir = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"

    count_before = store.count(collection=ingested_collection)
    assert count_before > 0

    # Ingest again
    ingest_folder(
        pdf_dir,
        store=store,
        embedder=fake_dense,
        sparse=fake_sparse,
        collection=ingested_collection,
        db=db,
    )
    count_after = store.count(collection=ingested_collection)
    assert count_after == count_before


def test_reingest_shortened_pdf_leaves_no_stale_chunks(db, test_collection, tmp_path):
    store = SecureStore()
    fake_dense = FakeDenseEmbedder(size=8)
    fake_sparse = FakeSparseEmbedder()
    styles = getSampleStyleSheet()

    temp_pdf = tmp_path / "temp_doc.pdf"

    # Step 1: Create 3-page PDF
    story = [
        Paragraph("Page 1 content", styles["Normal"]),
        PageBreak(),
        Paragraph("Page 2 content", styles["Normal"]),
        PageBreak(),
        Paragraph("Page 3 content", styles["Normal"]),
    ]
    doc = SimpleDocTemplate(str(temp_pdf), pagesize=letter)
    doc.build(story)

    # Ingest 3-page PDF
    ingest_pdf(temp_pdf, store=store, embedder=fake_dense, sparse=fake_sparse, collection=test_collection, db=db)
    points_3p = store.admin_scroll(limit=20, doc_id="temp_doc", collection=test_collection)
    assert len(points_3p) == 3

    # Step 2: Overwrite with 1-page PDF
    story_short = [Paragraph("Only Page 1 remains.", styles["Normal"])]
    doc_short = SimpleDocTemplate(str(temp_pdf), pagesize=letter)
    doc_short.build(story_short)

    # Re-ingest shortened PDF
    ingest_pdf(temp_pdf, store=store, embedder=fake_dense, sparse=fake_sparse, collection=test_collection, db=db)
    points_1p = store.admin_scroll(limit=20, doc_id="temp_doc", collection=test_collection)
    assert len(points_1p) == 1
    assert points_1p[0].payload["page"] == 1
    assert "Only Page 1 remains." in points_1p[0].payload["text"]


def test_payload_indexes_exist(test_collection):
    store = SecureStore()
    info = store.get_collection_info(collection=test_collection)
    schema = info.payload_schema

    expected_keywords = ["allowed_roles", "allowed_users", "owner_id", "doc_id", "source_type"]
    for k in expected_keywords:
        assert k in schema, f"Missing payload index for keyword field {k}"
        assert schema[k].data_type.name.lower() == "keyword"

    assert "classification" in schema
    assert schema["classification"].data_type.name.lower() == "integer"

    for b in ["is_public", "deleted"]:
        assert b in schema
        assert schema[b].data_type.name.lower() == "bool"


def test_only_store_py_imports_qdrant_client():
    backend_root = Path(__file__).resolve().parent.parent
    py_files = list(backend_root.rglob("*.py"))

    violations = []
    for py_file in py_files:
        # Normalize relative path
        rel_path = py_file.relative_to(backend_root).as_posix()
        if rel_path == "app/index/store.py":
            continue
        # Skip pycache or venv if present
        if ".venv" in rel_path or "__pycache__" in rel_path:
            continue

        content = py_file.read_text(encoding="utf-8")
        if "qdrant_client" in content:
            # Check for actual import statements
            lines = content.splitlines()
            for line_no, line in enumerate(lines, 1):
                clean_line = line.strip()
                if (clean_line.startswith("import qdrant_client") or
                    clean_line.startswith("from qdrant_client")):
                    violations.append(f"{rel_path}:{line_no} -> {clean_line}")

    assert not violations, f"Found unauthorized qdrant_client imports outside store.py:\n" + "\n".join(violations)


def test_demo_facts_catalog_matches_ingested_chunks(ingested_collection):
    store = SecureStore()
    facts_path = Path(__file__).resolve().parent.parent.parent / "data" / "demo_facts.json"
    assert facts_path.exists()
    facts = json.loads(facts_path.read_text(encoding="utf-8"))

    for fact in facts:
        doc_id = fact["doc_id"]
        page = fact["page"]
        text_target = fact["text"]

        points = store.admin_scroll(limit=50, doc_id=doc_id, collection=ingested_collection)
        matching = [
            p for p in points
            if p.payload.get("page") == page and text_target in p.payload.get("text", "")
        ]
        assert len(matching) > 0, f"Demo fact {fact['fact_id']!r} not found in doc {doc_id} on page {page}!"


# ── Slow Test: Real Sentence Transformers Model ──────────────────

@pytest.mark.slow
def test_real_bge_m3_dense_embedder():
    embedder = DenseEmbedder()
    sentences = [
        "VaultRAG is a secure multi-modal retrieval system.",
        "Access control boundaries are enforced at the retrieval layer.",
    ]
    vecs = embedder.embed(sentences)
    assert len(vecs) == 2
    dense_dim = embedder.dense_size
    assert len(vecs[0]) == dense_dim
    assert len(vecs[1]) == dense_dim

    # Check vectors are normalized (L2 norm ~ 1.0)
    norm0 = np.linalg.norm(vecs[0])
    norm1 = np.linalg.norm(vecs[1])
    assert pytest.approx(norm0, 1e-3) == 1.0
    assert pytest.approx(norm1, 1e-3) == 1.0
