"""
Tests for Step 4c Source Viewer endpoints:
- GET /source/{chunk_id}/view
- GET /source/{chunk_id}/page.png
- GET /source/{chunk_id}/pages

Verifies:
1. Identical 404 responses for forbidden vs nonexistent chunks.
2. Allowed user gets PNG with correct content-type and Cache-Control headers.
3. Rects are strictly bounded within [0..1].
4. No acl_tokens or absolute file paths leaked in any response.
5. Path traversal attempts are rejected.
6. Admin read sets admin_access=True in audit log.
7. DB row chunks return 404 for page.png.
8. Multi-page PDF permission check: user who can read page 1 but not page 2 gets 200 for page 1 and 404 for page 2.
"""

from io import BytesIO
from urllib.parse import quote
import pytest
from httpx import AsyncClient

from app.db.models import AuditLog, User
from app.index.schema import Chunk
from app.index.store import SecureStore
from app.storage.assets import asset_store
from tests.conftest import SEED_PASSWORD, TestSession, auth_header


@pytest.mark.asyncio
async def test_view_and_page_identical_404_forbidden_and_nonexistent(client: AsyncClient):
    """Forbidden and nonexistent chunks return identical 404 responses."""
    # Login as Asha (employee)
    r_login = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    assert r_login.status_code == 200
    t_asha = r_login.json()["access_token"]

    # Forbidden chunk (Apex contract - Finance only)
    chunk_forbidden = "vendor_contract_apex-p1-c1"
    q_forbidden = quote(chunk_forbidden, safe="")

    # Nonexistent chunk
    q_nonexistent = quote("nonexistent_chunk_id_xyz999", safe="")

    # 1. /view endpoint
    r_view_forb = await client.get(f"/source/{q_forbidden}/view", headers=auth_header(t_asha))
    r_view_none = await client.get(f"/source/{q_nonexistent}/view", headers=auth_header(t_asha))

    assert r_view_forb.status_code == 404
    assert r_view_none.status_code == 404
    assert r_view_forb.json() == r_view_none.json()
    assert r_view_forb.json() == {"detail": "Chunk not found"}

    # 2. /page.png endpoint
    r_page_forb = await client.get(f"/source/{q_forbidden}/page.png?page=1", headers=auth_header(t_asha))
    r_page_none = await client.get(f"/source/{q_nonexistent}/page.png?page=1", headers=auth_header(t_asha))

    assert r_page_forb.status_code == 404
    assert r_page_none.status_code == 404
    assert r_page_forb.json() == r_page_none.json()
    assert r_page_forb.json() == {"detail": "Chunk not found"}

    # 3. /pages endpoint
    r_pages_forb = await client.get(f"/source/{q_forbidden}/pages", headers=auth_header(t_asha))
    r_pages_none = await client.get(f"/source/{q_nonexistent}/pages", headers=auth_header(t_asha))

    assert r_pages_forb.status_code == 404
    assert r_pages_none.status_code == 404
    assert r_pages_forb.json() == r_pages_none.json()


@pytest.mark.asyncio
async def test_allowed_user_gets_png_and_valid_rects(client: AsyncClient):
    """Allowed user gets PNG image and rects bounded strictly between 0 and 1."""
    # Login as Karan (Finance Admin)
    r_login = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = r_login.json()["access_token"]

    chunk_id = "vendor_contract_apex-p1-c1"
    q_id = quote(chunk_id, safe="")

    # Call /view with highlight
    r_view = await client.get(f"/source/{q_id}/view?hl=437-590", headers=auth_header(t_karan))
    assert r_view.status_code == 200
    data = r_view.json()

    assert data["kind"] == "pdf_text"
    assert data["file"] == "vendor_contract_apex.pdf"
    assert data["page"] == 1
    assert data["match"] == "exact"
    assert "page_image_url" in data
    assert len(data["rects"]) > 0

    for rect in data["rects"]:
        assert 0.0 <= rect["x"] <= 1.0
        assert 0.0 <= rect["y"] <= 1.0
        assert 0.0 <= rect["w"] <= 1.0
        assert 0.0 <= rect["h"] <= 1.0
        assert rect["x"] + rect["w"] <= 1.001
        assert rect["y"] + rect["h"] <= 1.001

    # Call /page.png
    r_page = await client.get(f"/source/{q_id}/page.png?page=1", headers=auth_header(t_karan))
    assert r_page.status_code == 200
    assert r_page.headers["content-type"] == "image/png"
    assert "private" in r_page.headers.get("cache-control", "")
    assert len(r_page.content) > 1000


@pytest.mark.asyncio
async def test_no_leak_of_acl_tokens_or_file_paths(client: AsyncClient):
    """Never leak acl_tokens or absolute filesystem paths in any response."""
    r_login = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = r_login.json()["access_token"]

    for cid in ["vendor_contract_apex-p1-c1", "img:invoice_01_apex_apr.png#0"]:
        q_id = quote(cid, safe="")
        r_view = await client.get(f"/source/{q_id}/view", headers=auth_header(t_karan))
        assert r_view.status_code == 200
        raw_text = r_view.text

        assert "acl_tokens" not in raw_text
        assert "D:\\" not in raw_text
        assert "D:/" not in raw_text
        assert "/rag_demo_dataset/" not in raw_text
        assert "C:\\" not in raw_text


@pytest.mark.asyncio
async def test_db_row_page_image_returns_404(client: AsyncClient):
    """DB row chunks return 404 for page.png and valid metadata in /view."""
    # Login as Karan (Finance) who can read salaries
    r_login = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = r_login.json()["access_token"]

    chunk_id = "db:salaries#E1004:sensitive"
    q_id = quote(chunk_id, safe="")

    # /view
    r_view = await client.get(f"/source/{q_id}/view?hl=0-20", headers=auth_header(t_karan))
    assert r_view.status_code == 200
    v_data = r_view.json()
    assert v_data["kind"] == "db_row"
    assert v_data["row_id"] == "E1004"
    assert v_data["page_image_url"] is None
    assert v_data["rects"] == []

    # /page.png returns 404
    r_page = await client.get(f"/source/{q_id}/page.png", headers=auth_header(t_karan))
    assert r_page.status_code == 404
    assert r_page.json() == {"detail": "Chunk not found"}


@pytest.mark.asyncio
async def test_admin_access_flag_recorded_in_audit(client: AsyncClient):
    """Admin read records admin_access=True in audit log."""
    r_login = await client.post("/auth/login", json={"email": "admin@northwind.example", "password": SEED_PASSWORD})
    t_admin = r_login.json()["access_token"]

    chunk_id = "vendor_contract_apex-p1-c1"
    q_id = quote(chunk_id, safe="")

    r_view = await client.get(f"/source/{q_id}/view", headers=auth_header(t_admin))
    assert r_view.status_code == 200

    db = TestSession()
    try:
        admin_user = db.query(User).filter(User.external_id == "u_admin").first()
        log = (
            db.query(AuditLog)
            .filter(AuditLog.user_id == str(admin_user.id), AuditLog.event_type == "citation")
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.admin_access is True
        assert log.refused is False
    finally:
        db.close()


def test_asset_store_traversal_rejected():
    """AssetStore must strictly reject path traversal payloads."""
    with pytest.raises(ValueError, match="Path traversal"):
        asset_store.resolve_asset_path("../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal"):
        asset_store.resolve_asset_path("pdfs/../../../secret.txt")

    with pytest.raises(ValueError, match="Absolute paths forbidden"):
        asset_store.resolve_asset_path("/etc/shadow")

    with pytest.raises(ValueError, match="Absolute paths forbidden"):
        asset_store.resolve_asset_path("C:/Windows/System32/cmd.exe")


@pytest.mark.asyncio
async def test_path_traversal_endpoint_returns_404(client: AsyncClient):
    """Path traversal payloads in chunk IDs fail closed with 404."""
    r_login = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
    t_karan = r_login.json()["access_token"]

    for trav in [".._.._etc_passwd", "some..traversal", "traversal_attempt_99"]:
        r = await client.get(f"/source/{trav}/view", headers=auth_header(t_karan))
        assert r.status_code == 404
        assert r.json() == {"detail": "Chunk not found"}


@pytest.mark.asyncio
async def test_multi_page_pdf_page_permission_split(client: AsyncClient):
    """
    Requirement B.8:
    A user who can read page 1 of a document but not page 2 gets 200 for page 1
    and the identical 404 for page 2.
    """
    store = SecureStore()
    source_id = "pdf:board_minutes_2026_08.pdf"
    chunk_id_p1 = "test:split_doc#p1"
    chunk_id_p2 = "test:split_doc#p2"

    chunk1 = Chunk(
        chunk_id=chunk_id_p1,
        doc_id=source_id,
        source_doc="board_minutes_2026_08.pdf",
        source_id=source_id,
        source_type="pdf",
        source_name="board_minutes_2026_08",
        corpus="main",
        page=1,
        text="Board Minutes Page 1 test content for general employee",
        acl_tokens=["role:employee", "dept:Engineering", "role:admin"],
    )

    chunk2 = Chunk(
        chunk_id=chunk_id_p2,
        doc_id=source_id,
        source_doc="board_minutes_2026_08.pdf",
        source_id=source_id,
        source_type="pdf",
        source_name="board_minutes_2026_08",
        corpus="main",
        page=2,
        text="Board Minutes Page 2 confidential executive budget numbers",
        acl_tokens=["role:finance_admin", "dept:Finance", "role:admin"],
    )

    # Ingest dummy test points (dense and sparse dummy zero vectors)
    dummy_dense = [[0.0] * 1024, [0.0] * 1024]
    dummy_sparse = [{"indices": [1], "values": [1.0]}, {"indices": [2], "values": [1.0]}]
    store.upsert_chunks([chunk1, chunk2], dummy_dense, dummy_sparse)

    try:
        # 1. Login as Asha (role:employee, lacks role:finance_admin)
        r_asha = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
        t_asha = r_asha.json()["access_token"]

        # Asha calls /pages on chunk 1
        r_pages = await client.get(f"/source/{quote(chunk_id_p1, safe='')}/pages", headers=auth_header(t_asha))
        assert r_pages.status_code == 200
        readable_asha = r_pages.json()["readable_pages"]
        assert 1 in readable_asha
        assert 2 not in readable_asha

        # Asha calls /page.png?page=1 -> 200
        r_p1 = await client.get(f"/source/{quote(chunk_id_p1, safe='')}/page.png?page=1", headers=auth_header(t_asha))
        assert r_p1.status_code == 200
        assert r_p1.headers["content-type"] == "image/png"
        assert len(r_p1.content) > 1000

        # Asha calls /page.png?page=2 -> 404 (identical detail)
        r_p2 = await client.get(f"/source/{quote(chunk_id_p1, safe='')}/page.png?page=2", headers=auth_header(t_asha))
        assert r_p2.status_code == 404
        assert r_p2.json() == {"detail": "Chunk not found"}

        # 2. Login as Karan (role:finance_admin, allowed on page 2)
        r_karan = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
        t_karan = r_karan.json()["access_token"]

        # Karan calls /page.png?page=2 -> 200
        r_p2_karan = await client.get(f"/source/{quote(chunk_id_p2, safe='')}/page.png?page=2", headers=auth_header(t_karan))
        assert r_p2_karan.status_code == 200
        assert r_p2_karan.headers["content-type"] == "image/png"

    finally:
        # Clean up test points
        store.delete_points([chunk_id_p1, chunk_id_p2])
