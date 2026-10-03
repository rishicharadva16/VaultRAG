"""Health endpoint test."""

import pytest


@pytest.mark.asyncio
async def test_health_reports_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["postgres"]["status"] == "ok"
    assert data["qdrant"]["status"] == "ok"
