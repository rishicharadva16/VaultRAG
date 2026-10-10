"""
Tests for Step 5e Endpoints:
- GET /auth/demo-users (public, only visible active users, no emails/hashes)
- /admin/users guards: non-admin gets neutral 404, unauthenticated gets 401
- POST /admin/users: create user (always employee), duplicate email gives 422
- PATCH /admin/users/{id}: update fields, self-deactivation blocked
- Immediate rejection of deactivated users on next request
"""

import pytest
from app.db.models import AuditLog, User
from tests.conftest import SEED_PASSWORD, auth_header


async def _get_token(client, email: str, password: str = SEED_PASSWORD) -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_demo_users_endpoint_public_and_sanitized(client):
    """GET /auth/demo-users needs no auth and returns only visible active users without secrets."""
    resp = await client.get("/auth/demo-users")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # Exactly 4 demo users configured by default: Admin, Meera, Karan, Asha
    assert len(data) == 4

    names = {u["name"] for u in data}
    assert "System Admin" in names
    assert "Meera Iyer" in names
    assert "Karan Shah" in names
    assert "Asha Patel" in names

    # Verify schema and absence of sensitive fields
    for u in data:
        assert "id" in u
        assert "name" in u
        assert "department" in u
        assert "is_admin" in u
        assert "email" not in u
        assert "password" not in u
        assert "password_hash" not in u


@pytest.mark.asyncio
async def test_admin_users_guards_neutral_404_and_401(client):
    """Admin endpoints return 401 for unauthenticated and neutral 404 for non-admins."""
    # 1. Unauthenticated -> 401
    resp_unauth = await client.get("/admin/users")
    assert resp_unauth.status_code == 401

    resp_unauth_post = await client.post("/admin/users", json={
        "name": "Test", "email": "test@northwind.example", "password": "password123", "department": "HR"
    })
    assert resp_unauth_post.status_code == 401

    # 2. Authenticated non-admin (employee) -> 404 (neutral, indistinguishable from nonexistent)
    employee_token = await _get_token(client, "asha.patel@northwind.example")
    h_emp = auth_header(employee_token)

    resp_emp_get = await client.get("/admin/users", headers=h_emp)
    assert resp_emp_get.status_code == 404
    assert resp_emp_get.json()["detail"] == "Not found"

    resp_emp_post = await client.post("/admin/users", headers=h_emp, json={
        "name": "Test", "email": "test@northwind.example", "password": "password123", "department": "HR"
    })
    assert resp_emp_post.status_code == 404
    assert resp_emp_post.json()["detail"] == "Not found"

    resp_emp_patch = await client.patch("/admin/users/any-id", headers=h_emp, json={"name": "New"})
    assert resp_emp_patch.status_code == 404
    assert resp_emp_patch.json()["detail"] == "Not found"


@pytest.mark.asyncio
async def test_admin_create_user_and_duplicate_email(client, db):
    """POST /admin/users creates employee; duplicate email returns 422."""
    admin_token = await _get_token(client, "admin@northwind.example")
    h_admin = auth_header(admin_token)

    new_email = "vikram.malhotra@northwind.example"
    # Ensure cleanup first
    db.query(User).filter(User.email == new_email).delete()
    db.commit()

    try:
        # Create user
        resp = await client.post("/admin/users", headers=h_admin, json={
            "name": "Vikram Malhotra",
            "email": new_email,
            "department": "Engineering",
            "employee_id": "E1099",
            "password": "strongpassword123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == new_email
        assert data["department"] == "Engineering"
        assert data["employee_id"] == "E1099"
        assert data["is_admin"] is False
        assert data["is_active"] is True
        assert data["roles"] == ["employee"]

        # Duplicate email returns 422
        dup_resp = await client.post("/admin/users", headers=h_admin, json={
            "name": "Vikram Dup",
            "email": new_email,
            "department": "Engineering",
            "password": "strongpassword123",
        })
        assert dup_resp.status_code == 422
        assert "already registered" in dup_resp.json()["detail"].lower()

        # Audit log verification
        logs = db.query(AuditLog).filter(
            AuditLog.event == "admin.create_user"
        ).all()
        matching = [l for l in logs if l.details and l.details.get("email") == new_email]
        assert len(matching) >= 1
        assert "password" not in str(matching[-1].details)
    finally:
        db.query(User).filter(User.email == new_email).delete()
        db.commit()


@pytest.mark.asyncio
async def test_patch_user_and_prevent_self_deactivation(client, db):
    """PATCH /admin/users/{id} updates fields and blocks admin self-deactivation."""
    admin_token = await _get_token(client, "admin@northwind.example")
    h_admin = auth_header(admin_token)

    # 1. Self-deactivation blocked
    admin_user = db.query(User).filter(User.email == "admin@northwind.example").first()
    assert admin_user is not None

    self_deact_resp = await client.patch(
        f"/admin/users/{admin_user.id}",
        headers=h_admin,
        json={"is_active": False},
    )
    assert self_deact_resp.status_code == 400
    assert "cannot deactivate" in self_deact_resp.json()["detail"].lower()

    # 2. Patch normal user
    neha = db.query(User).filter(User.email == "neha.desai@northwind.example").first()
    assert neha is not None
    orig_name = neha.name

    try:
        patch_resp = await client.patch(
            f"/admin/users/{neha.id}",
            headers=h_admin,
            json={"name": "Neha Desai-Sharma", "shown_in_demo": True},
        )
        assert patch_resp.status_code == 200
        patched_data = patch_resp.json()
        assert patched_data["name"] == "Neha Desai-Sharma"
        assert patched_data["shown_in_demo"] is True

        # Demo users now includes Neha
        demo_resp = await client.get("/auth/demo-users")
        assert any(u["name"] == "Neha Desai-Sharma" for u in demo_resp.json())
    finally:
        # Revert Neha
        neha.name = orig_name
        neha.shown_in_demo = False
        db.commit()


@pytest.mark.asyncio
async def test_deactivated_user_rejected_immediately_on_next_request(client, db):
    """A user deactivated while holding a valid JWT is rejected on their very next request."""
    admin_token = await _get_token(client, "admin@northwind.example")
    h_admin = auth_header(admin_token)

    # Create temporary user
    temp_email = "temp.deact@northwind.example"
    db.query(User).filter(User.email == temp_email).delete()
    db.commit()

    create_resp = await client.post("/admin/users", headers=h_admin, json={
        "name": "Temp Deact",
        "email": temp_email,
        "department": "HR",
        "password": "temppassword123",
    })
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    try:
        # Log in as temp user
        user_token = await _get_token(client, temp_email, "temppassword123")
        h_user = auth_header(user_token)

        # Confirm valid call succeeds
        resp1 = await client.get("/auth/me", headers=h_user)
        assert resp1.status_code == 200
        assert resp1.json()["email"] == temp_email

        # Admin deactivates temp user
        deact_resp = await client.patch(
            f"/admin/users/{user_id}",
            headers=h_admin,
            json={"is_active": False},
        )
        assert deact_resp.status_code == 200
        assert deact_resp.json()["is_active"] is False

        # Temp user's next request with previously valid JWT is rejected immediately
        resp2 = await client.get("/auth/me", headers=h_user)
        assert resp2.status_code == 401

        # Attempt to login also fails
        login_fail = await client.post("/auth/login", json={"email": temp_email, "password": "temppassword123"})
        assert login_fail.status_code == 401
    finally:
        db.query(User).filter(User.email == temp_email).delete()
        db.commit()
