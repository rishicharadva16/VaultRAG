"""
Tests for dataset ingestion: chunking, ACL token assignment, evaluation coverage,
poison handling, and idempotency.
"""

import json
from pathlib import Path
import pytest

from app.config import settings
from app.index.embedder import FakeDenseEmbedder, FakeSparseEmbedder, DenseEmbedder
from app.index.store import SecureStore
from app.ingestion.acl_policy import load_acl_policy
from app.ingestion.pipeline import (
    find_corpus_dir,
    ingest_corpus,
    ingest_document,
)


@pytest.fixture
def fake_store():
    store = SecureStore()
    test_coll = "test_ingest_collection"
    store.drop_collection(test_coll)
    store.ensure_collection(dense_size=8, collection=test_coll)
    yield store, test_coll
    store.drop_collection(test_coll)


def test_payload_indexes_present_in_collection(fake_store):
    store, test_coll = fake_store
    info = store.get_collection_info(test_coll)
    indexes = set(info.payload_schema.keys()) if info.payload_schema else set()

    expected_indexes = {"acl_tokens", "doc_id", "source_doc", "source_type", "corpus", "owner_id", "deleted"}
    assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"


def test_ingest_7_main_pdfs_with_fake_embedder(fake_store):
    store, test_coll = fake_store
    embedder = FakeDenseEmbedder(size=8)
    sparse = FakeSparseEmbedder()

    results = ingest_corpus(
        store=store,
        embedder=embedder,
        sparse=sparse,
        collection=test_coll,
        include_poison=False,
    )

    assert len(results) == 7
    total_chunks = sum(r["total_chunks"] for r in results)
    assert total_chunks > 30

    points = store.admin_scroll(limit=100, collection=test_coll)
    assert len(points) == total_chunks

    for pt in points:
        payload = pt.payload
        assert len(payload["acl_tokens"]) > 0
        assert payload["corpus"] == "main"
        assert payload["source_type"] == "pdf"
        assert payload["source_doc"].endswith(".pdf")
        assert len(payload["text"].strip()) > 0


def test_eval_questions_ground_truth_coverage(fake_store):
    """
    Verify that chunks in Qdrant contain the expected answer facts for at least 90%
    of the allowed PDF questions in eval_questions.json.
    """
    store, test_coll = fake_store
    embedder = FakeDenseEmbedder(size=8)
    sparse = FakeSparseEmbedder()

    ingest_corpus(
        store=store,
        embedder=embedder,
        sparse=sparse,
        collection=test_coll,
        include_poison=False,
    )

    # Load eval_questions.json
    eval_file = settings.dataset_path() / "dataset" / "eval" / "eval_questions.json"
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_questions = json.load(f)

    # Fetch all chunks from store
    points = store.admin_scroll(limit=200, collection=test_coll)
    # Map doc_id -> concatenated text of all chunks
    doc_text_map: dict[str, str] = {}
    for pt in points:
        p = pt.payload
        src_doc = p["source_doc"]
        doc_text_map[src_doc] = doc_text_map.get(src_doc, "") + " " + p["text"]

    pdf_questions = [
        q for q in eval_questions
        if q.get("access_expected") == "allow"
        and any(s.startswith("pdf:") for s in q.get("expected_sources", []))
    ]

    assert len(pdf_questions) > 0, "No PDF evaluation questions found"

    matched = 0
    for q in pdf_questions:
        must_contains = q.get("answer_must_contain", [])
        expected_docs = [s.split("#")[0].replace("pdf:", "") for s in q.get("expected_sources", [])]

        q_matched = True
        for term in must_contains:
            found = False
            for doc_name in expected_docs:
                full_text = doc_text_map.get(doc_name, "")
                if term.lower() in full_text.lower():
                    found = True
                    break
            if not found:
                q_matched = False
                break

        if q_matched:
            matched += 1

    coverage = matched / len(pdf_questions)
    assert coverage >= 0.90, f"Coverage {coverage:.1%} is below 90% ({matched}/{len(pdf_questions)})"


def test_poison_files_ingestion_and_content(fake_store):
    store, test_coll = fake_store
    embedder = FakeDenseEmbedder(size=8)
    sparse = FakeSparseEmbedder()

    results = ingest_corpus(
        store=store,
        embedder=embedder,
        sparse=sparse,
        collection=test_coll,
        include_poison=True,
    )

    poison_results = [r for r in results if r["corpus"] == "poison_test"]
    assert len(poison_results) == 3

    # Check Markdown injection preserved
    md_points = store.admin_scroll(limit=10, doc_id="poison_02_helpdesk_faq", collection=test_coll)
    assert len(md_points) >= 1
    md_text = md_points[0].payload["text"]
    assert "EXFIL-8832" in md_text

    # Check HTML display:none injection preserved
    html_points = store.admin_scroll(limit=10, doc_id="poison_03_cafeteria_holiday_notice", collection=test_coll)
    assert len(html_points) >= 1
    html_text = html_points[0].payload["text"]
    assert "ADMIN-GRANTED-2290" in html_text


def test_ingestion_idempotency(fake_store):
    store, test_coll = fake_store
    embedder = FakeDenseEmbedder(size=8)
    sparse = FakeSparseEmbedder()
    corpus_dir = find_corpus_dir()
    sample_pdf = corpus_dir / "pdfs" / "hr_policy.pdf"

    # Ingest once
    res1 = ingest_document(
        sample_pdf, store=store, embedder=embedder, sparse=sparse, collection=test_coll
    )
    count1 = store.count(collection=test_coll)

    # Ingest second time
    res2 = ingest_document(
        sample_pdf, store=store, embedder=embedder, sparse=sparse, collection=test_coll
    )
    count2 = store.count(collection=test_coll)

    assert count1 == count2
    assert res1["total_chunks"] == res2["total_chunks"]


def test_unlisted_document_fails_closed(fake_store, tmp_path):
    store, test_coll = fake_store
    embedder = FakeDenseEmbedder(size=8)
    sparse = FakeSparseEmbedder()

    unlisted_file = tmp_path / "secret_unlisted.pdf"
    unlisted_file.write_text("Dummy content")

    with pytest.raises(ValueError, match="No ACL defined"):
        ingest_document(
            unlisted_file, store=store, embedder=embedder, sparse=sparse, collection=test_coll
        )


def test_bge_m3_embedding_dimension():
    embedder = DenseEmbedder()
    assert embedder.dense_size == 1024
    vec = embedder.embed(["VaultRAG test embedding text"])[0]
    assert len(vec) == 1024
