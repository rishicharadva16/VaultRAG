"""
Tests for Admin Access (Part D):
(a) admin search returns chunks from all main documents, none from poison_test;
(b) a normal user's results are unchanged by the admin flag;
(c) the admin token set is still only role:admin (no wildcard, no bypass);
(d) GET /citation/{chunk_id} works for admin on any main chunk and still returns 404 for nonexistent id;
(e) set_admin_access --off then --on round trip via the script function;
(f) every admin /ask, /search or /citation call writes an audit row with admin_access=true, and no document text.
"""

import json
import urllib.parse
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditLog, User
from app.index.store import SecureStore
from app.llm.provider import FakeLLM, set_llm, reset_llm
from app.security.principals import Principal, build_principal
from scripts.set_admin_access import get_status, set_access
from tests.conftest import SEED_PASSWORD, auth_header

pytestmark = pytest.mark.anyio


# ── (a) Admin search returns chunks from main documents, none from poison_test ──

def test_admin_search_main_only_no_poison():
    store = SecureStore()
    admin_p = Principal(user_id="u_admin", tokens=["role:admin"])

    # Search for general terms that match across dataset documents
    results = store.search(
        principal=admin_p,
        query="policy employee invoice board contract",
        top_k=20,
        include_poison=False,
    )

    assert len(results) > 0, "Admin search should return chunks when ADMIN_SEES_ALL is on"
    for r in results:
        assert r.corpus != "poison_test", f"Admin search leaked poison_test chunk: {r.chunk_id}"
        assert not r.source_id.startswith("poison:"), f"Admin search leaked poison source: {r.source_id}"

    # Also check all points in Qdrant: poison points contain role:admin, but search excludes them
    all_points = store.admin_scroll(limit=500)
    main_points = [p for p in all_points if (p.payload or {}).get("corpus") == "main"]
    poison_points = [p for p in all_points if (p.payload or {}).get("corpus") == "poison_test"]

    assert len(main_points) >= 46, f"Expected at least 46 main points, got {len(main_points)}"
    assert len(poison_points) == 8, f"Expected 8 poison points, got {len(poison_points)}"

    # All main points have role:admin
    for p in main_points:
        assert "role:admin" in p.payload.get("acl_tokens", []), f"Main point missing role:admin: {p.id}"


# ── (b) Normal user's results are unchanged by the admin flag ──

def test_normal_user_results_unchanged_by_admin_flag():
    store = SecureStore()
    asha_p = Principal(
        user_id="u_asha",
        tokens=["org:northwind", "role:employee", "dept:Engineering", "emp:E1004", "usr:u_asha"],
    )

    # Asha's results for HR notice query
    asha_results = store.search(
        principal=asha_p,
        query="What is the notice period for an L2 employee?",
        top_k=5,
    )

    assert len(asha_results) > 0
    # Every chunk returned for Asha must only be what Asha is permitted to see
    allowed_sources = {
        "pdf:hr_policy.pdf",
        "pdf:leave_policy.pdf",
        "pdf:travel_expense_policy.pdf",
        "pdf:it_security_policy.pdf",
        "db:employees",
    }
    for r in asha_results:
        assert r.source_id in allowed_sources, (
            f"Unexpected source for Asha: {r.source_id}"
        )


# ── (c) Admin token set is strictly role:admin (no wildcard, no bypass) ──

def test_admin_token_set_is_strictly_role_admin(db: Session):
    admin_user = db.query(User).filter(User.external_id == "u_admin").first()
    assert admin_user is not None

    p = build_principal(admin_user)
    assert p.user_id == str(admin_user.id)
    assert "role:admin" in p.tokens, f"Admin tokens must contain 'role:admin', got {p.tokens}"
    assert "org:northwind" in p.tokens
    assert not any(t.startswith("dept:") for t in p.tokens)
    assert "*" not in p.tokens
    assert "admin:*" not in p.tokens
    assert "role:*" not in p.tokens


# ── (d) GET /citation/{chunk_id} works for admin on any main chunk & returns 404 for nonexistent ──

async def test_admin_get_citation_on_main_chunk_and_404(client: AsyncClient):
    res = await client.post("/auth/login", json={
        "email": "admin@northwind.example", "password": SEED_PASSWORD
    })
    token = res.json()["access_token"]

    store = SecureStore()
    pts = store.admin_scroll(limit=10)
    main_pt = next(p for p in pts if (p.payload or {}).get("corpus") == "main")
    main_chunk_id = main_pt.payload["chunk_id"]

    # 1. Fetch valid chunk
    quoted_id = urllib.parse.quote(main_chunk_id, safe="")
    r_valid = await client.get(f"/citation/{quoted_id}", headers=auth_header(token))
    assert r_valid.status_code == 200
    body = r_valid.json()
    assert body["chunk_id"] == main_chunk_id
    assert len(body["text"]) > 0

    # 2. Fetch nonexistent chunk -> 404
    r_missing = await client.get("/citation/nonexistent-chunk-id-12345", headers=auth_header(token))
    assert r_missing.status_code == 404
    assert r_missing.json() == {"detail": "Chunk not found"}


# ── (e) set_admin_access --off then --on round trip via script function ──

def test_set_admin_access_round_trip():
    store = SecureStore()
    initial_status = get_status(store)
    total = initial_status["total_points"]

    try:
        # Turn OFF
        res_off = set_access(False, store)
        assert res_off["scanned"] == total
        assert res_off["changed"] == total
        status_off = get_status(store)
        assert status_off["admin_points"] == 0
        assert status_off["total_points"] == total

        # Turn ON
        res_on = set_access(True, store)
        assert res_on["scanned"] == total
        assert res_on["changed"] == total
        status_on = get_status(store)
        assert status_on["admin_points"] == total
        assert status_on["total_points"] == total

        # Idempotent check
        res_on_again = set_access(True, store)
        assert res_on_again["scanned"] == total
        assert res_on_again["changed"] == 0
        assert res_on_again["already_correct"] == total
    finally:
        set_access(True, store)


# ── (f) Every admin /ask, /search or /citation call writes audit row with admin_access=true, no doc text ──

async def test_admin_audit_logging_structured_fields(client: AsyncClient, db: Session):
    res = await client.post("/auth/login", json={
        "email": "admin@northwind.example", "password": SEED_PASSWORD
    })
    token = res.json()["access_token"]
    admin_user = db.query(User).filter(User.external_id == "u_admin").first()
    admin_id_str = str(admin_user.id)

    # 1. Search call
    r_search = await client.post("/search", headers=auth_header(token), json={"query": "Apex logistics contract"})
    assert r_search.status_code == 200

    search_log = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == admin_id_str, AuditLog.event_type == "search")
        .order_by(AuditLog.ts.desc())
        .first()
    )
    assert search_log is not None
    assert search_log.admin_access is True
    assert search_log.question_hash is not None
    assert search_log.question_length == len("Apex logistics contract")
    assert search_log.details is not None
    assert "query" not in search_log.details, "Raw query text must not be logged in audit details"
    assert "text" not in search_log.details, "Document text must never be logged"

    # 2. Citation call
    store = SecureStore()
    pts = store.admin_scroll(limit=1)
    chunk_id = pts[0].payload["chunk_id"]
    quoted_id = urllib.parse.quote(chunk_id, safe="")

    r_cit = await client.get(f"/citation/{quoted_id}", headers=auth_header(token))
    assert r_cit.status_code == 200

    cit_log = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == admin_id_str, AuditLog.event_type == "citation")
        .order_by(AuditLog.ts.desc())
        .first()
    )
    assert cit_log is not None
    assert cit_log.admin_access is True
    assert cit_log.chunk_count == 1
    assert "text" not in cit_log.details, "Chunk text must never be logged in citation audit"

    # 3. Ask call
    fake = FakeLLM()
    fake.set_responses(
        json.dumps({
            "answerable": True,
            "sentences": [{
                "text": "The fixed monthly service fee under the Apex contract is Rs 4,00,000 [1].",
                "citations": [1],
            }],
        })
    )
    set_llm(fake)
    try:
        r_ask = await client.post(
            "/ask",
            headers=auth_header(token),
            json={"question": "What is the monthly service fee under the Apex contract?"},
        )
        assert r_ask.status_code == 200
    finally:
        reset_llm()

    ask_log = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == admin_id_str, AuditLog.event_type == "ask")
        .order_by(AuditLog.ts.desc())
        .first()
    )
    assert ask_log is not None
    assert ask_log.admin_access is True
    assert ask_log.question_hash is not None
    assert ask_log.question_length > 0
    assert "question" not in ask_log.details, "Raw question text must not be logged in ask audit"
    assert "answer" not in ask_log.details, "Answer text must not be logged in ask audit"
    assert "text" not in ask_log.details, "Document text must not be logged in ask audit"
