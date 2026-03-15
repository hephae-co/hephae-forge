"""API tests for POST /api/auth/me — user creation and login sync."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


MOCK_USER = {
    "uid": "user-abc-123",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "https://lh3.googleusercontent.com/photo.jpg",
}


# ---------------------------------------------------------------------------
# Fixture: client with Firebase auth mocked
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    from hephae_api.main import app
    from hephae_api.lib.auth import verify_firebase_token

    app.dependency_overrides[verify_firebase_token] = lambda: MOCK_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(verify_firebase_token, None)


@pytest_asyncio.fixture
async def unauthed_client():
    """Client with NO auth override — real verify_firebase_token will reject."""
    from hephae_api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests: POST /api/auth/me
# ---------------------------------------------------------------------------

class TestAuthMe:
    @pytest.mark.asyncio
    async def test_creates_user_on_first_login(self, client):
        """First login should create user doc and return it."""
        now = datetime.now(timezone.utc)
        user_doc = {
            "uid": "user-abc-123",
            "email": "test@example.com",
            "displayName": "Test User",
            "photoURL": "https://lh3.googleusercontent.com/photo.jpg",
            "businesses": [],
            "createdAt": now,
            "lastLoginAt": now,
        }

        with patch(
            "hephae_api.routers.web.auth.get_or_create_user",
            new_callable=AsyncMock,
            return_value=user_doc,
        ) as mock_create:
            res = await client.post("/api/auth/me")

        assert res.status_code == 200
        data = res.json()
        assert data["uid"] == "user-abc-123"
        assert data["email"] == "test@example.com"
        assert data["displayName"] == "Test User"
        assert data["businesses"] == []

        # Verify get_or_create_user was called with correct args
        mock_create.assert_called_once_with(
            uid="user-abc-123",
            email="test@example.com",
            display_name="Test User",
            photo_url="https://lh3.googleusercontent.com/photo.jpg",
        )

    @pytest.mark.asyncio
    async def test_returns_existing_user_with_businesses(self, client):
        """Subsequent login should return existing user with their businesses."""
        user_doc = {
            "uid": "user-abc-123",
            "email": "test@example.com",
            "displayName": "Test User",
            "photoURL": "https://lh3.googleusercontent.com/photo.jpg",
            "businesses": ["joes-pizza", "bobs-burgers"],
            "createdAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "lastLoginAt": datetime(2026, 3, 11, tzinfo=timezone.utc),
        }

        with patch(
            "hephae_api.routers.web.auth.get_or_create_user",
            new_callable=AsyncMock,
            return_value=user_doc,
        ):
            res = await client.post("/api/auth/me")

        assert res.status_code == 200
        data = res.json()
        assert data["businesses"] == ["joes-pizza", "bobs-burgers"]

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self, client):
        """User without photoURL or displayName should still succeed."""
        user_doc = {
            "uid": "user-abc-123",
            "email": "test@example.com",
            "businesses": [],
        }

        with patch(
            "hephae_api.routers.web.auth.get_or_create_user",
            new_callable=AsyncMock,
            return_value=user_doc,
        ):
            res = await client.post("/api/auth/me")

        assert res.status_code == 200
        data = res.json()
        assert data["uid"] == "user-abc-123"
        assert data.get("displayName") is None
        assert data.get("photoURL") is None

    @pytest.mark.asyncio
    async def test_requires_auth_token(self, unauthed_client):
        """Missing Firebase token should return 401."""
        res = await unauthed_client.post("/api/auth/me")
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_500_on_firestore_failure(self, client):
        """If get_or_create_user raises, endpoint should return 500."""
        with patch(
            "hephae_api.routers.web.auth.get_or_create_user",
            new_callable=AsyncMock,
            side_effect=Exception("Firestore connection failed"),
        ):
            res = await client.post("/api/auth/me")

        assert res.status_code == 500
        assert "error" in res.json()
