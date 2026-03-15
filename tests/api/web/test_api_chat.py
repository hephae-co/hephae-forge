"""API tests for POST /api/chat — session management and auth integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


MOCK_USER = {"uid": "user-chat-1", "email": "chatter@example.com", "name": "Chat User", "picture": None}


# ---------------------------------------------------------------------------
# Fixture: client with optional auth (chat supports guests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def authed_client():
    """Client with authenticated user."""
    from hephae_api.main import app
    from hephae_api.lib.auth import optional_firebase_user

    app.dependency_overrides[optional_firebase_user] = lambda: MOCK_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(optional_firebase_user, None)


@pytest_asyncio.fixture
async def guest_client():
    """Client with no auth (guest mode)."""
    from hephae_api.main import app
    from hephae_api.lib.auth import optional_firebase_user

    app.dependency_overrides[optional_firebase_user] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(optional_firebase_user, None)


# ---------------------------------------------------------------------------
# Mock for ADK Runner — prevents real Gemini calls
# ---------------------------------------------------------------------------

def _mock_runner_events(text: str = "Hello! How can I help?"):
    """Create a mock async generator that yields an event with text."""
    from unittest.mock import MagicMock

    part = MagicMock()
    part.thought = False
    part.text = text

    content = MagicMock()
    content.parts = [part]

    event = MagicMock()
    event.content = content

    async def mock_run_async(**kwargs):
        yield event

    return mock_run_async


# ---------------------------------------------------------------------------
# Tests: Authentication in chat
# ---------------------------------------------------------------------------

class TestChatAuth:
    @pytest.mark.asyncio
    async def test_authenticated_user_gets_real_uid(self, authed_client):
        """Authenticated user should use their Firebase uid, not 'anonymous'."""
        mock_session = MagicMock()
        mock_session.id = "session-abc"

        with (
            patch("hephae_api.routers.web.chat._session_service") as mock_svc,
            patch("hephae_api.routers.web.chat.Runner") as MockRunner,
        ):
            mock_svc.get_session = AsyncMock(return_value=None)
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockRunner.return_value.run_async = _mock_runner_events()

            res = await authed_client.post("/api/chat", json={
                "messages": [{"role": "user", "text": "Hello"}],
            })

        assert res.status_code == 200

        # Verify create_session was called with authenticated uid
        create_call = mock_svc.create_session.call_args
        assert create_call.kwargs.get("user_id") == "user-chat-1" or create_call[1].get("user_id") == "user-chat-1"

    @pytest.mark.asyncio
    async def test_guest_user_gets_anonymous_uid(self, guest_client):
        """Guest user (no token) should use 'anonymous' as uid."""
        mock_session = MagicMock()
        mock_session.id = "session-guest"

        with (
            patch("hephae_api.routers.web.chat._session_service") as mock_svc,
            patch("hephae_api.routers.web.chat.Runner") as MockRunner,
        ):
            mock_svc.get_session = AsyncMock(return_value=None)
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockRunner.return_value.run_async = _mock_runner_events()

            res = await guest_client.post("/api/chat", json={
                "messages": [{"role": "user", "text": "Hello"}],
            })

        assert res.status_code == 200

        # Verify create_session was called with "anonymous"
        create_call = mock_svc.create_session.call_args
        user_id = create_call.kwargs.get("user_id") or create_call[1].get("user_id")
        assert user_id == "anonymous"


# ---------------------------------------------------------------------------
# Tests: Session management
# ---------------------------------------------------------------------------

class TestChatSession:
    @pytest.mark.asyncio
    async def test_creates_new_session_when_no_id(self, authed_client):
        """No sessionId → creates a new session, returns sessionId in response."""
        mock_session = MagicMock()
        mock_session.id = "new-session-123"

        with (
            patch("hephae_api.routers.web.chat._session_service") as mock_svc,
            patch("hephae_api.routers.web.chat.Runner") as MockRunner,
        ):
            mock_svc.get_session = AsyncMock(return_value=None)
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockRunner.return_value.run_async = _mock_runner_events()

            res = await authed_client.post("/api/chat", json={
                "messages": [{"role": "user", "text": "Hello"}],
            })

        assert res.status_code == 200
        assert res.json()["sessionId"] == "new-session-123"

    @pytest.mark.asyncio
    async def test_reuses_existing_session_when_id_provided(self, authed_client):
        """Providing sessionId → retrieves existing session, no new creation."""
        existing_session = MagicMock()
        existing_session.id = "existing-sess-456"

        with (
            patch("hephae_api.routers.web.chat._session_service") as mock_svc,
            patch("hephae_api.routers.web.chat.Runner") as MockRunner,
        ):
            mock_svc.get_session = AsyncMock(return_value=existing_session)
            MockRunner.return_value.run_async = _mock_runner_events()

            res = await authed_client.post("/api/chat", json={
                "messages": [{"role": "user", "text": "Follow-up question"}],
                "sessionId": "existing-sess-456",
            })

        assert res.status_code == 200
        assert res.json()["sessionId"] == "existing-sess-456"

        # Should NOT have called create_session
        mock_svc.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_session_id_in_response(self, guest_client):
        """Response always includes sessionId for client to persist."""
        mock_session = MagicMock()
        mock_session.id = "sess-for-guest"

        with (
            patch("hephae_api.routers.web.chat._session_service") as mock_svc,
            patch("hephae_api.routers.web.chat.Runner") as MockRunner,
        ):
            mock_svc.get_session = AsyncMock(return_value=None)
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockRunner.return_value.run_async = _mock_runner_events()

            res = await guest_client.post("/api/chat", json={
                "messages": [{"role": "user", "text": "Hi"}],
            })

        assert "sessionId" in res.json()


# ---------------------------------------------------------------------------
# Tests: Input validation
# ---------------------------------------------------------------------------

class TestChatValidation:
    @pytest.mark.asyncio
    async def test_rejects_empty_messages(self, authed_client):
        res = await authed_client.post("/api/chat", json={
            "messages": [],
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_missing_messages(self, authed_client):
        res = await authed_client.post("/api/chat", json={})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_empty_text(self, authed_client):
        res = await authed_client.post("/api/chat", json={
            "messages": [{"role": "user", "text": ""}],
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_non_list_messages(self, authed_client):
        res = await authed_client.post("/api/chat", json={
            "messages": "not a list",
        })
        assert res.status_code == 400
