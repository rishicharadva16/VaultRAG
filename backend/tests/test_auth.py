"""Auth tests: login, token validation, role reloading, inactive user, password rules."""

import datetime
import pytest
import jwt as pyjwt

from app.config import settings
from app.db.models import User
from tests.conftest import SEED_PASSWORD, SEED_USERS, auth_header


@pytest.mark.asyncio
async def test_login_succeeds_for_all_seeded_users(client):
    for u in SEED_USERS:
        resp = await client.post("/auth/login", json={"email": u["email"], "password": SEED_PASSWORD})
        assert resp.status_code == 200, f"Login failed for {u['email']}: {resp.text}"
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_with_northwind_example_domain(client):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_wrong_password_returns_401(client):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": "wrongpwd1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unknown_email_returns_401_same_message(client):
    resp_wrong_pw = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": "wrongpwd1"})
    resp_unknown = await client.post("/auth/login", json={"email": "nobody@x.com", "password": "wrongpwd1"})
    assert resp_wrong_pw.status_code == 401
    assert resp_unknown.status_code == 401
    assert resp_wrong_pw.json()["detail"] == resp_unknown.json()["detail"]


@pytest.mark.asyncio
async def test_me_returns_correct_role_for_all_users(client):
    for u in SEED_USERS:
        resp = await client.post("/auth/login", json={"email": u["email"], "password": SEED_PASSWORD})
        token = resp.json()["access_token"]
        me = await client.get("/auth/me", headers=auth_header(token))
        assert me.status_code == 200
        assert me.json()["roles"] == u["roles"]


@pytest.mark.asyncio
async def test_me_returns_employee_id_and_dept_for_asha(client):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]
    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    data = me.json()
    assert data["employee_id"] == "E1004"
    assert data["department"] == "Engineering"
    assert data["external_id"] == "u_asha"
    assert data["roles"] == ["employee"]


@pytest.mark.asyncio
async def test_me_admin_has_none_employee_id_and_dept(client):
    resp = await client.post("/auth/login", json={"email": "admin@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]
    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    data = me.json()
    assert data["employee_id"] is None
    assert data["department"] is None
    assert data["roles"] == ["admin"]


@pytest.mark.asyncio
async def test_register_disabled_by_default_returns_403(client):
    resp = await client.post("/auth/register", json={
        "name": "DisabledReg", "email": "disabled@northwind.example", "password": "password123",
    })
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Registration is disabled"


@pytest.mark.asyncio
async def test_user_with_empty_roles_gets_200_on_me(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_SELF_REGISTER", True)
    resp = await client.post("/auth/register", json={
        "name": "NoRolesUser", "email": "noroles@northwind.example", "password": "password123",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["roles"] == []

    # Cleanup
    user = db.query(User).filter(User.email == "noroles@northwind.example").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_tampered_token_returns_401(client):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]
    tampered = token[:-4] + "XXXX"
    me = await client.get("/auth/me", headers=auth_header(tampered))
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": "fake-id",
        "iat": now - datetime.timedelta(hours=2),
        "exp": now - datetime.timedelta(hours=1),
        "jti": "test-jti",
    }
    expired_token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    me = await client.get("/auth/me", headers=auth_header(expired_token))
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_returns_401(client, db):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]

    user = db.query(User).filter(User.email == "asha.patel@northwind.example").first()
    user.active = False
    db.commit()

    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 401

    user.active = True
    db.commit()


@pytest.mark.asyncio
async def test_role_change_reflected_without_new_token(client, db):
    """Changing roles in the DB shows up on /me immediately (no new login needed)."""
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]

    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.json()["roles"] == ["employee"]

    user = db.query(User).filter(User.email == "asha.patel@northwind.example").first()
    user.roles = ["employee", "manager"]
    db.commit()

    me2 = await client.get("/auth/me", headers=auth_header(token))
    assert "manager" in me2.json()["roles"]

    user.roles = ["employee"]
    db.commit()


# ── A1: /me alias ──

@pytest.mark.asyncio
async def test_me_and_auth_me_return_identical_bodies(client):
    resp = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
    token = resp.json()["access_token"]
    h = auth_header(token)

    r1 = await client.get("/auth/me", headers=h)
    r2 = await client.get("/me", headers=h)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


# ── A2: Bearer security scheme ──

@pytest.mark.asyncio
async def test_openapi_has_bearer_scheme(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schemas = resp.json().get("components", {}).get("securitySchemes", {})
    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemas.values())


@pytest.mark.asyncio
async def test_no_auth_header_returns_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


# ── A3: CORS ──

@pytest.mark.asyncio
async def test_cors_allows_valid_origin(client):
    resp = await client.options("/health", headers={
        "Origin": "http://127.0.0.1:8080",
        "Access-Control-Request-Method": "GET",
    })
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:8080"


@pytest.mark.asyncio
async def test_cors_blocks_evil_origin(client):
    resp = await client.options("/health", headers={
        "Origin": "http://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert "access-control-allow-origin" not in resp.headers


# ── A5: Password validation ──

@pytest.mark.asyncio
async def test_register_rejects_7_char_password(client, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_SELF_REGISTER", True)
    resp = await client.post("/auth/register", json={
        "name": "Short", "email": "short@northwind.example", "password": "1234567",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_accepts_8_char_password(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_SELF_REGISTER", True)
    resp = await client.post("/auth/register", json={
        "name": "Eight", "email": "eight@northwind.example", "password": "12345678",
    })
    assert resp.status_code == 201
    # Cleanup
    user = db.query(User).filter(User.email == "eight@northwind.example").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_register_rejects_73_byte_password(client, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_SELF_REGISTER", True)
    # 73 ASCII chars = 73 bytes, exceeds bcrypt's 72-byte limit
    long_pw = "A" * 73
    resp = await client.post("/auth/register", json={
        "name": "Long", "email": "long@northwind.example", "password": long_pw,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_overlong_password_returns_401(client):
    """Over-long password on login returns the same generic 401, not a 500."""
    long_pw = "A" * 100
    resp = await client.post("/auth/login", json={
        "email": "asha.patel@northwind.example", "password": long_pw,
    })
    assert resp.status_code == 401
