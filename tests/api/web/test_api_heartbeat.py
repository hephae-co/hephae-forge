"""API tests for the heartbeat router (POST/GET/PATCH/DELETE /api/heartbeat)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Shared mock user
# ---------------------------------------------------------------------------

MOCK_USER = {"uid": "user-123", "email": "test@example.com", "name": "Test User", "picture": None}

MOCK_HEARTBEAT = {
    "id": "hb-001",
    "uid": "user-123",
    "businessSlug": "joes-pizza",
    "businessName": "Joe's Pizza",
    "capabilities": ["seo", "margin"],
    "frequency": "weekly",
    "dayOfWeek": 1,
    "active": True,
    "createdAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
    "lastRunAt": None,
    "nextRunAfter": datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc),
    "lastSnapshot": {},
    "totalRuns": 0,
    "consecutiveOks": 0,
}


# ---------------------------------------------------------------------------
# Fixture: client with auth mocked
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async test client with Firebase auth mocked via dependency_overrides."""
    from backend.main import app
    from backend.lib.auth import verify_firebase_token

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
    async def test_creates_heartbeat_success(self, client):
        with patch(
            "hephae_db.firestore.heartbeats.create_heartbeat",
            new_callable=AsyncMock,
            return_value="new-hb-id",
        ):
            res = await client.post("/api/heartbeat", json={
                "businessSlug": "joes-pizza",
                "businessName": "Joe's Pizza",
                "capabilities": ["seo", "margin", "traffic"],
                "dayOfWeek": 1,
            })

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["id"] == "new-hb-id"

    @pytest.mark.asyncio
    async def test_rejects_invalid_capabilities(self, client):
        res = await client.post("/api/heartbeat", json={
            "businessSlug": "joes-pizza",
            "businessName": "Joe's Pizza",
            "capabilities": ["seo", "invalid_cap"],
        })

        assert res.status_code == 400
        assert "invalid" in res.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_empty_capabilities(self, client):
        res = await client.post("/api/heartbeat", json={
            "businessSlug": "joes-pizza",
            "businessName": "Joe's Pizza",
            "capabilities": [],
        })

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_missing_fields(self, client):
        res = await client.post("/api/heartbeat", json={
            "businessSlug": "joes-pizza",
            # missing businessName and capabilities
        })

        assert res.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio
    async def test_requires_auth(self):
        """Without auth token, should get 401."""
        # No auth mock — use real verify_firebase_token which will reject
        from backend.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/heartbeat", json={
                "businessSlug": "test",
                "businessName": "Test",
                "capabilities": ["seo"],
            })

        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Tests: GET /api/heartbeat
# ---------------------------------------------------------------------------

class TestListHeartbeats:
    @pytest.mark.asyncio
    async def test_lists_user_heartbeats(self, client):
        heartbeats = [
            {**MOCK_HEARTBEAT, "id": "hb-1"},
            {**MOCK_HEARTBEAT, "id": "hb-2", "businessName": "Bob's Burgers"},
        ]

        with patch(
            "hephae_db.firestore.heartbeats.get_user_heartbeats",
            new_callable=AsyncMock,
            return_value=heartbeats,
        ):
            res = await client.get("/api/heartbeat")

        assert res.status_code == 200
        data = res.json()
        assert len(data["heartbeats"]) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self, client):
        with patch(
            "hephae_db.firestore.heartbeats.get_user_heartbeats",
            new_callable=AsyncMock,
            return_value=[],
        ):
            res = await client.get("/api/heartbeat")

        assert res.status_code == 200
        assert res.json()["heartbeats"] == []


# ---------------------------------------------------------------------------
# Tests: PATCH /api/heartbeat/{id}
# ---------------------------------------------------------------------------

class TestUpdateHeartbeat:
    @pytest.mark.asyncio
    async def test_updates_capabilities(self, client):
        with (
            patch(
                "hephae_db.firestore.heartbeats.get_heartbeat",
                new_callable=AsyncMock,
                return_value=MOCK_HEARTBEAT,
            ),
            patch(
                "hephae_db.firestore.heartbeats.update_heartbeat",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            res = await client.patch("/api/heartbeat/hb-001", json={
                "capabilities": ["seo", "traffic", "competitive"],
            })

        assert res.status_code == 200
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "hb-001"
        assert call_args[0][1]["capabilities"] == ["seo", "traffic", "competitive"]

    @pytest.mark.asyncio
    async def test_pauses_heartbeat(self, client):
        with (
            patch(
                "hephae_db.firestore.heartbeats.get_heartbeat",
                new_callable=AsyncMock,
                return_value=MOCK_HEARTBEAT,
            ),
            patch(
                "hephae_db.firestore.heartbeats.update_heartbeat",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            res = await client.patch("/api/heartbeat/hb-001", json={"active": False})

        assert res.status_code == 200
        assert mock_update.call_args[0][1]["active"] is False

    @pytest.mark.asyncio
    async def test_rejects_update_for_other_user(self, client):
        other_user_hb = {**MOCK_HEARTBEAT, "uid": "other-user-456"}

        with patch(
            "hephae_db.firestore.heartbeats.get_heartbeat",
            new_callable=AsyncMock,
            return_value=other_user_hb,
        ):
            res = await client.patch("/api/heartbeat/hb-001", json={"active": False})

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_rejects_update_for_nonexistent(self, client):
        with patch(
            "hephae_db.firestore.heartbeats.get_heartbeat",
            new_callable=AsyncMock,
            return_value=None,
        ):
            res = await client.patch("/api/heartbeat/nonexistent", json={"active": False})

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_rejects_invalid_capability_on_update(self, client):
        with patch(
            "hephae_db.firestore.heartbeats.get_heartbeat",
            new_callable=AsyncMock,
            return_value=MOCK_HEARTBEAT,
        ):
            res = await client.patch("/api/heartbeat/hb-001", json={
                "capabilities": ["seo", "bad_cap"],
            })

        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Tests: DELETE /api/heartbeat/{id}
# ---------------------------------------------------------------------------

class TestDeleteHeartbeat:
    @pytest.mark.asyncio
    async def test_deletes_own_heartbeat(self, client):
        with (
            patch(
                "hephae_db.firestore.heartbeats.get_heartbeat",
                new_callable=AsyncMock,
                return_value=MOCK_HEARTBEAT,
            ),
            patch(
                "hephae_db.firestore.heartbeats.delete_heartbeat",
                new_callable=AsyncMock,
            ) as mock_delete,
        ):
            res = await client.delete("/api/heartbeat/hb-001")

        assert res.status_code == 200
        assert res.json()["success"] is True
        mock_delete.assert_called_once_with("hb-001")

    @pytest.mark.asyncio
    async def test_rejects_delete_for_other_user(self, client):
        other_user_hb = {**MOCK_HEARTBEAT, "uid": "other-user-456"}

        with patch(
            "hephae_db.firestore.heartbeats.get_heartbeat",
            new_callable=AsyncMock,
            return_value=other_user_hb,
        ):
            res = await client.delete("/api/heartbeat/hb-001")

        assert res.status_code == 404
