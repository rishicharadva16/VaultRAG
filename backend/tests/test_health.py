"""Health endpoint test."""

import pytest


@pytest.mark.asyncio
async def test_health_reports_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["postgres"]["status"] == "ok"
    assert data["qdrant"]["status"] == "ok"


@pytest.mark.asyncio
async def test_root_reports_ok(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_cors_allowed_and_forbidden_origins(client):
    """Request from an allowed origin gets CORS header; forbidden origin does not."""
    # Allowed origin gets access-control-allow-origin
    resp_allowed = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp_allowed.status_code == 200
    assert resp_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Forbidden origin does not get access-control-allow-origin
    resp_forbidden = await client.get("/health", headers={"Origin": "http://attacker.example.com"})
    assert resp_forbidden.status_code == 200
    assert "access-control-allow-origin" not in resp_forbidden.headers

