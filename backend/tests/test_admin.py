"""Admin endpoint tests: RBAC, user creation, audit trail, deactivation."""

import pytest

from app.db.models import AuditLog, User
from tests.conftest import SEED_PASSWORD, auth_header


async def _admin_token(client):
    resp = await client.post("/auth/login", json={"email": "priya@vaultrag.local", "password": SEED_PASSWORD})
    return resp.json()["access_token"]


async def _non_admin_token(client):
    resp = await client.post("/auth/login", json={"email": "rahul@vaultrag.local", "password": SEED_PASSWORD})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_non_admin_gets_403(client):
    token = await _non_admin_token(client)
    h = auth_header(token)
    assert (await client.get("/admin/users", headers=h)).status_code == 403
    assert (await client.post("/admin/users", headers=h, json={
        "name": "X", "email": "x@x.com", "password": "password1", "roles": [], "clearance": 1
    })).status_code == 403


@pytest.mark.asyncio
async def test_admin_creates_user_who_can_login(client, db):
    token = await _admin_token(client)
    h = auth_header(token)

    resp = await client.post("/admin/users", headers=h, json={
        "name": "TestUser", "email": "test_admin_create@vaultrag.local",
        "password": "testpassword", "roles": ["viewer"], "clearance": 2,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["roles"] == ["viewer"]
    assert data["clearance"] == 2

    login_resp = await client.post("/auth/login", json={
        "email": "test_admin_create@vaultrag.local", "password": "testpassword"
    })
    assert login_resp.status_code == 200
    new_token = login_resp.json()["access_token"]

    me = await client.get("/auth/me", headers=auth_header(new_token))
    assert me.json()["roles"] == ["viewer"]

    user = db.query(User).filter(User.email == "test_admin_create@vaultrag.local").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_self_registered_user_has_no_roles(client, db):
    resp = await client.post("/auth/register", json={
        "name": "SelfReg", "email": "selfreg@vaultrag.local", "password": "password1",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.json()["roles"] == []
    assert me.json()["clearance"] == 1

    user = db.query(User).filter(User.email == "selfreg@vaultrag.local").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_register_ignores_roles_in_body(client, db):
    """Even if the client sends roles in the register body, they are ignored."""
    resp = await client.post("/auth/register", json={
        "name": "Sneaky", "email": "sneaky@vaultrag.local", "password": "password1",
        "roles": ["admin"], "clearance": 3,
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = await client.get("/auth/me", headers=auth_header(token))
    assert me.json()["roles"] == []
    assert me.json()["clearance"] == 1

    user = db.query(User).filter(User.email == "sneaky@vaultrag.local").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_deactivating_user_makes_token_return_401(client, db):
    token = await _admin_token(client)
    h = auth_header(token)

    resp = await client.post("/admin/users", headers=h, json={
        "name": "ToDeactivate", "email": "deact@vaultrag.local",
        "password": "password1", "roles": ["viewer"], "clearance": 1,
    })
    user_id = resp.json()["id"]

    login_resp = await client.post("/auth/login", json={
        "email": "deact@vaultrag.local", "password": "password1"
    })
    user_token = login_resp.json()["access_token"]

    deact = await client.put(f"/admin/users/{user_id}/active", headers=h,
                             json={"active": False})
    assert deact.status_code == 200

    me = await client.get("/auth/me", headers=auth_header(user_token))
    assert me.status_code == 401

    user = db.query(User).filter(User.email == "deact@vaultrag.local").first()
    if user:
        db.delete(user)
        db.commit()


@pytest.mark.asyncio
async def test_admin_actions_appear_in_audit_log(client, db):
    token = await _admin_token(client)
    h = auth_header(token)

    db.query(AuditLog).delete()
    db.commit()

    resp = await client.post("/admin/users", headers=h, json={
        "name": "AuditTest", "email": "audit_test@vaultrag.local",
        "password": "password1", "roles": ["viewer"], "clearance": 1,
    })
    assert resp.status_code == 201

    logs = db.query(AuditLog).filter(AuditLog.event == "admin.create_user").all()
    assert len(logs) >= 1
    assert logs[-1].details["email"] == "audit_test@vaultrag.local"

    user = db.query(User).filter(User.email == "audit_test@vaultrag.local").first()
    if user:
        db.delete(user)
        db.commit()
