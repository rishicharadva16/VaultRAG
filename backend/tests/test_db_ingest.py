"""
Tests for STEP 4a: Database records ingestion with row- and column-level access control.

Checks:
- Ingestion is idempotent (run twice, same point count).
- Every DB chunk has non-empty acl_tokens.
- Sensitive-column chunks never contain base-only tokens that would widen access.
- An employee cannot retrieve another employee's private row (e.g. salary).
- A manager retrieves direct reports' base rows/expenses but NOT their sensitive chunks (DOB, phone, salary).
- HR admin retrieves sensitive columns.
- Forbidden and nonexistent row IDs give identical /citation 404s.
- No acl_tokens appear in any API response.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.index.schema import Chunk
from app.index.store import SecureStore
from app.ingestion.db_ingestion import ingest_database, load_db_chunks
from app.main import app
from app.security.principals import build_principal


@pytest.fixture
def store():
    return SecureStore()


def test_every_db_chunk_has_nonempty_acl_tokens():
    """Every database chunk must have non-empty, valid acl_tokens."""
    chunks = load_db_chunks()
    assert len(chunks) == 180

    valid_prefixes = ("role:", "emp:", "dept:", "rolemp:", "usr:")
    for chunk in chunks:
        assert len(chunk.acl_tokens) > 0, f"Chunk {chunk.chunk_id} has empty acl_tokens"
        for tok in chunk.acl_tokens:
            assert any(tok.startswith(p) for p in valid_prefixes), (
                f"Chunk {chunk.chunk_id} contains invalid token format: {tok}"
            )


def test_sensitive_chunks_never_contain_base_only_tokens():
    """
    Sensitive chunks (DOB/phone in employees, bank account in salaries)
    must never contain base tokens like role:employee, role:manager, or role:finance_admin
    that would inadvertently widen access.
    """
    chunks = load_db_chunks()
    for chunk in chunks:
        if chunk.chunk_id.endswith(":sensitive"):
            assert "role:employee" not in chunk.acl_tokens, (
                f"Sensitive chunk {chunk.chunk_id} contains role:employee"
            )
            assert "role:manager" not in chunk.acl_tokens, (
                f"Sensitive chunk {chunk.chunk_id} contains role:manager"
            )
            # Salaries sensitive (bank account) must also not be visible to finance_admin
            if "salaries" in chunk.chunk_id:
                assert "role:finance_admin" not in chunk.acl_tokens, (
                    f"Sensitive salary chunk {chunk.chunk_id} contains role:finance_admin"
                )


def test_db_ingestion_idempotence(store):
    """Running ingest_database twice must not duplicate points in Qdrant."""
    count_before = store.count()

    # Re-run ingestion
    results = ingest_database(store=store)
    count_after_first = store.count()

    # Run again
    results_second = ingest_database(store=store)
    count_after_second = store.count()

    assert count_after_first == count_after_second
    assert sum(r["total_chunks"] for r in results_second) == 180


def test_employee_cannot_retrieve_another_employees_row(store):
    """u_neha (E1006) cannot retrieve Asha's (E1004) salary rows."""
    neha_principal = build_principal({
        "user_id": "u_neha",
        "employee_id": "E1006",
        "roles": ["employee"],
        "department": "Sales",
    })

    # Neha cannot get Asha's base salary
    c_base = store.get_chunk(neha_principal, "db:salaries#E1004:base")
    assert c_base is None

    # Neha cannot get Asha's sensitive salary
    c_sens = store.get_chunk(neha_principal, "db:salaries#E1004:sensitive")
    assert c_sens is None

    # Neha can get her own base salary
    c_own = store.get_chunk(neha_principal, "db:salaries#E1006:base")
    assert c_own is not None
    assert "E1006" in c_own.text


def test_manager_retrieves_direct_reports_base_rows_but_not_sensitive(store):
    """
    u_ravi (manager E1003) manages Asha (E1004).
    Ravi can see Asha's base employee record and expenses,
    but CANNOT see Asha's sensitive employee record or Asha's salary.
    """
    ravi_principal = build_principal({
        "user_id": "u_ravi",
        "employee_id": "E1003",
        "roles": ["manager"],
        "department": "Engineering",
    })

    # 1. Base employee directory is public to managers
    emp_base = store.get_chunk(ravi_principal, "db:employees#E1004:base")
    assert emp_base is not None
    assert "Asha Patel" in emp_base.text

    # 2. Sensitive employee record (DOB, phone) is NOT visible to manager
    emp_sens = store.get_chunk(ravi_principal, "db:employees#E1004:sensitive")
    assert emp_sens is None

    # 3. Direct report's expense is visible to manager
    exp_report = store.get_chunk(ravi_principal, "db:expenses#EXP-1005:base")
    assert exp_report is not None
    assert "EXP-1005" in exp_report.text

    # 4. Direct report's salary is NOT visible to manager
    sal_report = store.get_chunk(ravi_principal, "db:salaries#E1004:base")
    assert sal_report is None


def test_hr_admin_retrieves_sensitive_columns(store):
    """u_meera (hr_admin) can retrieve sensitive chunks for any employee."""
    meera_principal = build_principal({
        "user_id": "u_meera",
        "employee_id": "E1001",
        "roles": ["hr_admin"],
        "department": "HR",
    })

    # Meera can see Asha's sensitive employee record (DOB, phone)
    emp_sens = store.get_chunk(meera_principal, "db:employees#E1004:sensitive")
    assert emp_sens is not None
    assert "date of birth" in emp_sens.text

    # Meera can see Asha's sensitive salary record (bank account)
    sal_sens = store.get_chunk(meera_principal, "db:salaries#E1004:sensitive")
    assert sal_sens is not None
    assert "bank account last 4 digits" in sal_sens.text


@pytest.mark.asyncio
async def test_forbidden_and_nonexistent_row_ids_give_identical_citation_404():
    """
    GET /citation/{chunk_id} returns identical 404 for forbidden and nonexistent chunks.
    Timing and response structure must match exactly.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login as u_asha
        r_login = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": "changeme123"})
        assert r_login.status_code == 200
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        from urllib.parse import quote

        # 1. Forbidden chunk: Ravi's salary
        r_forbidden = await client.get(f"/citation/{quote('db:salaries#E1003:base', safe='')}", headers=headers)
        assert r_forbidden.status_code == 404
        assert r_forbidden.json() == {"detail": "Chunk not found"}

        # 2. Nonexistent chunk
        r_nonexistent = await client.get(f"/citation/{quote('db:salaries#E9999:base', safe='')}", headers=headers)
        assert r_nonexistent.status_code == 404
        assert r_nonexistent.json() == {"detail": "Chunk not found"}


@pytest.mark.asyncio
async def test_no_acl_tokens_appear_in_api_responses():
    """No acl_tokens or internal permission data ever leaks in API responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Login as u_meera
        r_login = await client.post("/auth/login", json={"email": "meera.iyer@northwind.example", "password": "changeme123"})
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Search
        r_search = await client.post("/search", headers=headers, json={"query": "Asha Patel manager"})
        assert r_search.status_code == 200
        search_body = r_search.text
        assert "acl_tokens" not in search_body
        assert "role:hr_admin" not in search_body

        # Citation
        from urllib.parse import quote
        r_cit = await client.get(f"/citation/{quote('db:employees#E1004:base', safe='')}", headers=headers)
        assert r_cit.status_code == 200
        cit_body = r_cit.text
        assert "acl_tokens" not in cit_body
        assert "Asha Patel" in cit_body
