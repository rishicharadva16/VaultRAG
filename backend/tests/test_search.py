"""
Search and ACL enforcement test suite.

Verifies:
  - Filter construction and fail-closed behavior (empty tokens -> no Qdrant call).
  - Principal tokens built from database user on every request without re-login.
  - Authentication checks (missing token -> 401, deactivated user -> 401, tampered -> 401).
  - Access control separation:
      * Asha cannot see vendor contract, finance memo, or board minutes.
      * Ravi (manager) and Karan (finance_admin) see vendor contract.
      * Karan (finance_admin) sees finance memo.
      * Meera (hr_admin) sees board minutes, but not finance memo or vendor contract.
      * Admin sees 0 documents.
  - Byte-for-byte identical response for forbidden documents vs nonexistent documents.
  - Poison corpus exclusion by default.
  - Rate limiting enforcement (429 Too Many Requests).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

from app.config import settings
from app.db.models import User
from app.index.store import SecureStore
from app.security.principals import Principal, build_principal
from tests.conftest import SEED_PASSWORD, auth_header

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Filter Construction & Fail-Closed
# ---------------------------------------------------------------------------

def test_filter_construction_empty_tokens_no_qdrant_call(monkeypatch):
    """If principal has empty tokens, SecureStore.search returns [] without calling Qdrant."""
    store = SecureStore()
    mock_query_points = MagicMock()
    monkeypatch.setattr(store._client, "query_points", mock_query_points)

    empty_principal = Principal(user_id="test_user", tokens=[])
    results = store.search(principal=empty_principal, query="leave policy", top_k=5)

    assert results == []
    mock_query_points.assert_not_called()


def test_filter_construction_present_on_prefetches_and_query(monkeypatch):
    """The access filter must be attached to both dense and sparse prefetches and query_filter."""
    store = SecureStore()
    mock_response = MagicMock()
    mock_response.points = []
    mock_query_points = MagicMock(return_value=mock_response)
    monkeypatch.setattr(store._client, "query_points", mock_query_points)

    principal = Principal(user_id="u_asha", tokens=["role:employee", "dept:Engineering"])
    fake_vectors = ([0.1] * 1024, {"indices": [1, 2], "values": [0.5, 0.8]})

    store.search(principal=principal, query=fake_vectors, top_k=5, include_poison=False)

    assert mock_query_points.called
    kwargs = mock_query_points.call_args.kwargs

    # Check prefetches
    prefetches = kwargs.get("prefetch")
    assert len(prefetches) == 2
    dense_pref, sparse_pref = prefetches[0], prefetches[1]

    # Verify access filter on dense prefetch
    assert dense_pref.filter is not None
    must_keys = [c.key for c in dense_pref.filter.must]
    assert "acl_tokens" in must_keys
    must_not_keys = [c.key for c in dense_pref.filter.must_not]
    assert "deleted" in must_not_keys
    assert "corpus" in must_not_keys

    # Verify access filter on sparse prefetch
    assert sparse_pref.filter is not None
    assert [c.key for c in sparse_pref.filter.must] == ["acl_tokens"]

    # Verify access filter on outer query_filter
    query_filter = kwargs.get("query_filter")
    assert query_filter is not None
    assert [c.key for c in query_filter.must] == ["acl_tokens"]


# ---------------------------------------------------------------------------
# Principal Reload from DB on Request
# ---------------------------------------------------------------------------

async def test_principal_role_change_reflected_without_relogin(client: AsyncClient, db: Session):
    """Changing user role in DB immediately updates access tokens on next request without new login."""
    # 1. Login as Asha (employee)
    res = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    assert res.status_code == 200
    token = res.json()["access_token"]

    # 2. Asha searches vendor contract -> forbidden, 0 chunks from vendor_contract_apex.pdf
    search_res = await client.post("/search", headers=auth_header(token), json={"query": "Apex vendor contract value", "top_k": 5})
    assert search_res.status_code == 200
    sources_before = [r["source_id"] for r in search_res.json()["results"]]
    assert "pdf:vendor_contract_apex.pdf" not in sources_before

    # 3. Elevate Asha in DB to manager
    user = db.query(User).filter(User.external_id == "u_asha").first()
    user.roles = ["manager"]
    db.commit()

    try:
        # 4. Same token now searches and retrieves vendor contract
        search_res2 = await client.post("/search", headers=auth_header(token), json={"query": "Apex vendor contract value", "top_k": 5})
        assert search_res2.status_code == 200
        sources_after = [r["source_id"] for r in search_res2.json()["results"]]
        assert "pdf:vendor_contract_apex.pdf" in sources_after
    finally:
        # Revert role
        user.roles = ["employee"]
        db.commit()


# ---------------------------------------------------------------------------
# Authentication & Deactivation
# ---------------------------------------------------------------------------

async def test_search_without_token_returns_401(client: AsyncClient):
    res = await client.post("/search", json={"query": "company leave policy"})
    assert res.status_code == 401


async def test_search_with_tampered_token_returns_401(client: AsyncClient):
    res = await client.post("/search", headers=auth_header("invalid.tampered.token"), json={"query": "company leave policy"})
    assert res.status_code == 401


async def test_search_with_deactivated_user_returns_401(client: AsyncClient, db: Session):
    # Login as Neha
    res = await client.post("/auth/login", json={"email": "neha.desai@northwind.example", "password": SEED_PASSWORD})
    assert res.status_code == 200
    token = res.json()["access_token"]

    user = db.query(User).filter(User.external_id == "u_neha").first()
    user.active = False
    db.commit()

    try:
        search_res = await client.post("/search", headers=auth_header(token), json={"query": "leave policy"})
        assert search_res.status_code == 401
    finally:
        user.active = True
        db.commit()


# ---------------------------------------------------------------------------
# Access Control Separation: Asha, Ravi, Karan, Meera, Admin
# ---------------------------------------------------------------------------

async def test_acl_separation_vendor_contract(client: AsyncClient):
    """Asha gets no Apex chunks; Ravi and Karan do."""
    # Login as Asha
    res = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    t_asha = res.json()["access_token"]

    # Login as Ravi
    res = await client.post("/auth/login", json={"email": "ravi.menon@northwind.example", "password": SEED_PASSWORD})
    t_ravi = res.json()["access_token"]

    # Login as Karan
    res = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = res.json()["access_token"]

    query = "Apex vendor contract value"

    # Asha (employee) -> no Apex contract chunks
    r_asha = await client.post("/search", headers=auth_header(t_asha), json={"query": query})
    sources_asha = [item["source_id"] for item in r_asha.json()["results"]]
    assert "pdf:vendor_contract_apex.pdf" not in sources_asha

    # Ravi (manager) -> retrieves Apex contract
    r_ravi = await client.post("/search", headers=auth_header(t_ravi), json={"query": query})
    sources_ravi = [item["source_id"] for item in r_ravi.json()["results"]]
    assert "pdf:vendor_contract_apex.pdf" in sources_ravi

    # Karan (finance_admin) -> retrieves Apex contract
    r_karan = await client.post("/search", headers=auth_header(t_karan), json={"query": query})
    sources_karan = [item["source_id"] for item in r_karan.json()["results"]]
    assert "pdf:vendor_contract_apex.pdf" in sources_karan


async def test_acl_separation_finance_memo_and_board_minutes(client: AsyncClient):
    """Asha gets neither; Karan gets finance memo; Meera gets board minutes but not finance memo."""
    # Login Asha
    res = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    t_asha = res.json()["access_token"]

    # Login Karan (finance_admin)
    res = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = res.json()["access_token"]

    # Login Meera (hr_admin)
    res = await client.post("/auth/login", json={"email": "meera.iyer@northwind.example", "password": SEED_PASSWORD})
    t_meera = res.json()["access_token"]

    memo_q = "Q2 FY27 budget variance revenue targets finance memo"
    board_q = "August board meeting resolutions dividends"

    # Asha gets neither
    r_asha_memo = await client.post("/search", headers=auth_header(t_asha), json={"query": memo_q})
    assert "pdf:finance_memo_q2_fy27.pdf" not in [i["source_id"] for i in r_asha_memo.json()["results"]]

    r_asha_board = await client.post("/search", headers=auth_header(t_asha), json={"query": board_q})
    assert "pdf:board_minutes_2026_08.pdf" not in [i["source_id"] for i in r_asha_board.json()["results"]]

    # Karan gets finance memo
    r_karan_memo = await client.post("/search", headers=auth_header(t_karan), json={"query": memo_q})
    assert "pdf:finance_memo_q2_fy27.pdf" in [i["source_id"] for i in r_karan_memo.json()["results"]]

    # Meera gets board minutes, but NOT finance memo
    r_meera_board = await client.post("/search", headers=auth_header(t_meera), json={"query": board_q})
    assert "pdf:board_minutes_2026_08.pdf" in [i["source_id"] for i in r_meera_board.json()["results"]]

    r_meera_memo = await client.post("/search", headers=auth_header(t_meera), json={"query": memo_q})
    assert "pdf:finance_memo_q2_fy27.pdf" not in [i["source_id"] for i in r_meera_memo.json()["results"]]


async def test_admin_gets_zero_results(client: AsyncClient):
    """u_admin has role:admin which appears in no document ACL, so gets 0 results for any query."""
    res = await client.post("/auth/login", json={"email": "admin@northwind.example", "password": SEED_PASSWORD})
    assert res.status_code == 200
    t_admin = res.json()["access_token"]

    queries = [
        "What is the leave policy?",
        "Apex vendor contract value",
        "August board minutes resolutions",
        "IT security requirements",
    ]
    for q in queries:
        resp = await client.post("/search", headers=auth_header(t_admin), json={"query": q})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["results"] == []


# ---------------------------------------------------------------------------
# Identical Empty Response Shape
# ---------------------------------------------------------------------------

async def test_identical_empty_response_forbidden_vs_nonexistent(client: AsyncClient):
    """The response for forbidden document and nonexistent document must be byte-for-byte identical."""
    res = await client.post("/auth/login", json={"email": "admin@northwind.example", "password": SEED_PASSWORD})
    token = res.json()["access_token"]

    # Forbidden: Admin querying Apex vendor contract
    res_forbidden = await client.post("/search", headers=auth_header(token), json={"query": "Apex vendor contract value"})

    # Nonexistent: Admin querying non-existent topic
    res_nonexistent = await client.post("/search", headers=auth_header(token), json={"query": "quantum gravity propulsion system specifications"})

    assert res_forbidden.status_code == 200
    assert res_nonexistent.status_code == 200

    body_forbidden = res_forbidden.json()
    body_nonexistent = res_nonexistent.json()

    expected = {
        "results": [],
        "count": 0,
        "message": "No accessible results found.",
    }
    assert body_forbidden == expected
    assert body_nonexistent == expected


# ---------------------------------------------------------------------------
# Poison Corpus Exclusion
# ---------------------------------------------------------------------------

async def test_poison_corpus_never_returned_by_default(client: AsyncClient):
    """Poison documents are never returned in search by default."""
    res = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = res.json()["access_token"]

    resp = await client.post("/search", headers=auth_header(token), json={"query": "vendor onboarding checklist bank account transfer"})
    assert resp.status_code == 200
    for item in resp.json()["results"]:
        assert not item["source_id"].startswith("poison:")
        assert "poison" not in item["file"].lower()


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

async def test_search_rate_limiting(client: AsyncClient, db: Session, monkeypatch):
    """Excessive requests return 429 Too Many Requests."""
    res = await client.post("/auth/login", json={"email": "neha.desai@northwind.example", "password": SEED_PASSWORD})
    token = res.json()["access_token"]

    # Temporarily set rate limit to 3 requests per minute for testing
    from app.api import search as search_module
    monkeypatch.setattr(search_module.settings, "SEARCH_RATE_LIMIT_PER_MINUTE", 3)

    # Clear prior timestamps for Neha
    from app.db.models import User
    neha_user = db.query(User).filter(User.external_id == "u_neha").first()
    search_module._user_request_timestamps[str(neha_user.id)].clear()

    # Make 3 allowed requests
    for _ in range(3):
        r = await client.post("/search", headers=auth_header(token), json={"query": "leave policy"})
        assert r.status_code == 200

    # 4th request must be blocked with 429
    r_blocked = await client.post("/search", headers=auth_header(token), json={"query": "leave policy"})
    assert r_blocked.status_code == 429
    assert "Rate limit exceeded" in r_blocked.json()["detail"]
    assert r_blocked.status_code == 429
    assert "Rate limit exceeded" in r_blocked.json()["detail"]
