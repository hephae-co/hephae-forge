"""Unit tests for /api/heartbeat CRUD routes.

Covers: POST/GET/PATCH/DELETE with auth, 401 when missing auth.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


MOCK_USER = {"uid": "user-123", "email": "user@example.com", "name": "Test User", "picture": None}

SAMPLE_HEARTBEAT_DOC = {
    "id": "hb-001",
    "uid": "user-123",
    "businessSlug": "joes-pizza",
    "businessName": "Joe's Pizza",
    "capabilities": ["seo", "traffic"],
    "dayOfWeek": 1,
    "active": True,
    "frequency": "weekly",
    "createdAt": "2026-03-01T00:00:00",
    "lastRunAt": None,
    "nextRunAfter": "2026-03-10T13:00:00",
    "lastSnapshot": {},
    "totalRuns": 0,
    "consecutiveOks": 0,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def authed_client():
    """Client with Firebase token dependency overridden."""
    from hephae_api.main import app
    from hephae_api.lib.auth import verify_firebase_token

    app.dependency_overrides[verify_firebase_token] = lambda: MOCK_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(verify_firebase_token, None)


# ---------------------------------------------------------------------------
# Tests: POST /api/heartbeat
# ---------------------------------------------------------------------------

class TestCreateHeartbeat:
    @pytest.mark.asyncio
    async def test_creates_heartbeat_successfully(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.create_heartbeat", new_callable=AsyncMock, return_value="hb-001"):
            res = await authed_client.post("/api/heartbeat", json={
                "businessSlug": "joes-pizza",
                "businessName": "Joe's Pizza",
                "capabilities": ["seo", "traffic"],
                "dayOfWeek": 1,
            })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["id"] == "hb-001"

    @pytest.mark.asyncio
    async def test_400_when_invalid_capability(self, authed_client):
        res = await authed_client.post("/api/heartbeat", json={
            "businessSlug": "joes-pizza",
            "businessName": "Joe's Pizza",
            "capabilities": ["invalid-cap"],
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_400_when_no_capabilities(self, authed_client):
        res = await authed_client.post("/api/heartbeat", json={
            "businessSlug": "joes-pizza",
            "businessName": "Joe's Pizza",
            "capabilities": [],
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_401_when_no_auth(self):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/heartbeat", json={
                "businessSlug": "joes-pizza",
                "businessName": "Joe's Pizza",
                "capabilities": ["seo"],
            })
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Tests: GET /api/heartbeat
# ---------------------------------------------------------------------------

class TestListHeartbeats:
    @pytest.mark.asyncio
    async def test_lists_user_heartbeats(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.get_user_heartbeats", new_callable=AsyncMock, return_value=[SAMPLE_HEARTBEAT_DOC]):
            res = await authed_client.get("/api/heartbeat")
        assert res.status_code == 200
        data = res.json()
        assert "heartbeats" in data
        assert len(data["heartbeats"]) == 1
        assert data["heartbeats"][0]["id"] == "hb-001"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.get_user_heartbeats", new_callable=AsyncMock, return_value=[]):
            res = await authed_client.get("/api/heartbeat")
        assert res.status_code == 200
        assert res.json()["heartbeats"] == []

    @pytest.mark.asyncio
    async def test_401_when_no_auth(self):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/heartbeat")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Tests: PATCH /api/heartbeat/{id}
# ---------------------------------------------------------------------------

class TestUpdateHeartbeat:
    @pytest.mark.asyncio
    async def test_updates_heartbeat_successfully(self, authed_client):
        with (
            patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=SAMPLE_HEARTBEAT_DOC),
            patch("hephae_db.firestore.heartbeats.update_heartbeat", new_callable=AsyncMock),
        ):
            res = await authed_client.patch("/api/heartbeat/hb-001", json={"active": False})
        assert res.status_code == 200
        assert res.json()["success"] is True

    @pytest.mark.asyncio
    async def test_404_when_heartbeat_not_found(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=None):
            res = await authed_client.patch("/api/heartbeat/nonexistent", json={"active": True})
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_404_when_heartbeat_belongs_to_other_user(self, authed_client):
        other_user_hb = {**SAMPLE_HEARTBEAT_DOC, "uid": "other-user-456"}
        with patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=other_user_hb):
            res = await authed_client.patch("/api/heartbeat/hb-001", json={"active": True})
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_400_when_invalid_capability_in_update(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=SAMPLE_HEARTBEAT_DOC):
            res = await authed_client.patch("/api/heartbeat/hb-001", json={"capabilities": ["bad-cap"]})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_401_when_no_auth(self):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.patch("/api/heartbeat/hb-001", json={"active": False})
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Tests: DELETE /api/heartbeat/{id}
# ---------------------------------------------------------------------------

class TestDeleteHeartbeat:
    @pytest.mark.asyncio
    async def test_deletes_heartbeat_successfully(self, authed_client):
        with (
            patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=SAMPLE_HEARTBEAT_DOC),
            patch("hephae_db.firestore.heartbeats.delete_heartbeat", new_callable=AsyncMock),
        ):
            res = await authed_client.delete("/api/heartbeat/hb-001")
        assert res.status_code == 200
        assert res.json()["success"] is True

    @pytest.mark.asyncio
    async def test_404_when_heartbeat_not_found(self, authed_client):
        with patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=None):
            res = await authed_client.delete("/api/heartbeat/nonexistent")
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_404_when_belongs_to_other_user(self, authed_client):
        other_hb = {**SAMPLE_HEARTBEAT_DOC, "uid": "other-456"}
        with patch("hephae_db.firestore.heartbeats.get_heartbeat", new_callable=AsyncMock, return_value=other_hb):
            res = await authed_client.delete("/api/heartbeat/hb-001")
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_401_when_no_auth(self):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.delete("/api/heartbeat/hb-001")
        assert res.status_code == 401
