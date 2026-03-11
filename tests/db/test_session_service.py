"""Tests for FirestoreSessionService."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from packages.db.hephae_db.firestore.session_service import FirestoreSessionService

@pytest.mark.asyncio
async def test_create_session_guest():
    """Verify guest sessions have short TTL and correct flags."""
    service = FirestoreSessionService()

    with patch("packages.db.hephae_db.firestore.session_service.get_db") as mock_get_db:
        mock_doc = MagicMock()
        mock_get_db.return_value.collection.return_value.document.return_value = mock_doc

        session = await service.create_session(
            app_name="app", user_id="guest", session_id="sess-123", state={"key": "val"}
        )

        assert session.id == "sess-123"
        args, kwargs = mock_doc.set.call_args
        data = args[0]
        assert data["userId"] == "guest"
        assert data["isPermanent"] is False
        # Guest TTL should be ~24 hours
        assert data["deleteAt"] > datetime.utcnow() - timedelta(minutes=1)

@pytest.mark.asyncio
async def test_create_session_logged_in():
    """Verify logged-in user sessions have long TTL."""
    service = FirestoreSessionService()

    with patch("packages.db.hephae_db.firestore.session_service.get_db") as mock_get_db:
        mock_doc = MagicMock()
        mock_get_db.return_value.collection.return_value.document.return_value = mock_doc

        session = await service.create_session(
            app_name="app", user_id="user-456", session_id="sess-456", state={}
        )

        args, kwargs = mock_doc.set.call_args
        data = args[0]
        assert data["isPermanent"] is True
        # User TTL should be ~30 days
        assert data["deleteAt"] > datetime.utcnow() + timedelta(days=29)

@pytest.mark.asyncio
async def test_prune_session():
    """Verify heavy fields are removed during pruning."""
    service = FirestoreSessionService()

    with patch("packages.db.hephae_db.firestore.session_service.get_db") as mock_get_db:
        mock_doc = MagicMock()
        mock_get_db.return_value.collection.return_value.document.return_value = mock_doc

        await service.prune_session("sess-123")

        args, kwargs = mock_doc.update.call_args
        updates = args[0]
        assert "state.rawSiteData" in updates
        assert "state.gemini_cache_name" in updates
