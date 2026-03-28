"""Unit tests for hephae_db.firestore.heartbeats module.

NOTE: This file still uses heavy mocks — mock cleanup needed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_heartbeat_doc(doc_id: str = "hb-001", **overrides) -> MagicMock:
    """Create a mock Firestore DocumentSnapshot."""
    data = {
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
        **overrides,
    }
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _mock_db():
    """Return a mock Firestore client with chainable collection()."""
    db = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Tests: create_heartbeat
# ---------------------------------------------------------------------------

class TestCreateHeartbeat:
    @pytest.mark.asyncio
    async def test_creates_new_heartbeat(self):
        db = _mock_db()
        col = db.collection.return_value

        # No existing heartbeats
        col.where.return_value.where.return_value.limit.return_value.get.return_value = []

        doc_ref = MagicMock()
        doc_ref.id = "new-hb-id"
        col.document.return_value = doc_ref

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import create_heartbeat

            result = await create_heartbeat(
                uid="user-123",
                business_slug="joes-pizza",
                business_name="Joe's Pizza",
                capabilities=["seo", "margin"],
                day_of_week=1,
            )

        assert result == "new-hb-id"
        doc_ref.set.assert_called_once()
        call_data = doc_ref.set.call_args[0][0]
        assert call_data["uid"] == "user-123"
        assert call_data["businessSlug"] == "joes-pizza"
        assert call_data["capabilities"] == ["seo", "margin"]
        assert call_data["active"] is True
        assert call_data["totalRuns"] == 0

    @pytest.mark.asyncio
    async def test_returns_existing_heartbeat_if_duplicate(self):
        db = _mock_db()
        col = db.collection.return_value

        existing_doc = _make_heartbeat_doc("existing-hb")
        col.where.return_value.where.return_value.limit.return_value.get.return_value = [existing_doc]

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import create_heartbeat

            result = await create_heartbeat(
                uid="user-123",
                business_slug="joes-pizza",
                business_name="Joe's Pizza",
                capabilities=["seo"],
            )

        assert result == "existing-hb"
        # Should NOT create a new document
        col.document.return_value.set.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: get_user_heartbeats
# ---------------------------------------------------------------------------

class TestGetUserHeartbeats:
    @pytest.mark.asyncio
    async def test_returns_heartbeats_with_ids(self):
        db = _mock_db()
        docs = [_make_heartbeat_doc("hb-1"), _make_heartbeat_doc("hb-2")]
        db.collection.return_value.where.return_value.order_by.return_value.get.return_value = docs

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import get_user_heartbeats

            results = await get_user_heartbeats("user-123")

        assert len(results) == 2
        assert results[0]["id"] == "hb-1"
        assert results[1]["id"] == "hb-2"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self):
        db = _mock_db()
        db.collection.return_value.where.return_value.order_by.return_value.get.return_value = []

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import get_user_heartbeats

            results = await get_user_heartbeats("user-no-heartbeats")

        assert results == []


# ---------------------------------------------------------------------------
# Tests: get_heartbeat
# ---------------------------------------------------------------------------

class TestGetHeartbeat:
    @pytest.mark.asyncio
    async def test_returns_heartbeat_with_id(self):
        db = _mock_db()
        doc = _make_heartbeat_doc("hb-001")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import get_heartbeat

            result = await get_heartbeat("hb-001")

        assert result is not None
        assert result["id"] == "hb-001"
        assert result["businessSlug"] == "joes-pizza"

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import get_heartbeat

            result = await get_heartbeat("nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: update_heartbeat
# ---------------------------------------------------------------------------

class TestUpdateHeartbeat:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import update_heartbeat

            await update_heartbeat("hb-001", {"active": False})

        doc_ref.update.assert_called_once()
        call_data = doc_ref.update.call_args[0][0]
        assert call_data["active"] is False

    @pytest.mark.asyncio
    async def test_recomputes_next_run_when_day_changes(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import update_heartbeat

            await update_heartbeat("hb-001", {"dayOfWeek": 5})

        call_data = doc_ref.update.call_args[0][0]
        assert "nextRunAfter" in call_data
        assert call_data["dayOfWeek"] == 5


# ---------------------------------------------------------------------------
# Tests: delete_heartbeat
# ---------------------------------------------------------------------------

class TestDeleteHeartbeat:
    @pytest.mark.asyncio
    async def test_deletes_document(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import delete_heartbeat

            await delete_heartbeat("hb-001")

        doc_ref.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: get_due_heartbeats
# ---------------------------------------------------------------------------

class TestGetDueHeartbeats:
    @pytest.mark.asyncio
    async def test_returns_due_active_heartbeats(self):
        db = _mock_db()
        docs = [_make_heartbeat_doc("hb-due-1"), _make_heartbeat_doc("hb-due-2")]
        db.collection.return_value.where.return_value.where.return_value.order_by.return_value.get.return_value = docs

        with patch("hephae_db.firestore.heartbeats.get_db", return_value=db):
            from hephae_db.firestore.heartbeats import get_due_heartbeats

            now = datetime(2026, 3, 11, tzinfo=timezone.utc)
            results = await get_due_heartbeats(now)

        assert len(results) == 2
        assert results[0]["id"] == "hb-due-1"


# ---------------------------------------------------------------------------
# Tests: _next_weekday helper
# ---------------------------------------------------------------------------

class TestNextWeekday:
    def test_returns_future_date(self):
        from hephae_db.firestore.heartbeats import _next_weekday

        result = _next_weekday(day_of_week=0)  # Monday
        assert result > datetime.now(timezone.utc)
        assert result.weekday() == 0

    def test_returns_correct_hour(self):
        from hephae_db.firestore.heartbeats import _next_weekday

        result = _next_weekday(day_of_week=3, hour=15)
        assert result.hour == 15
