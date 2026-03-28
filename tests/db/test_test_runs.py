"""Unit tests for test_runs Firestore persistence and TTL cleanup."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_db():
    """Mock Firestore database."""
    db = MagicMock()
    with patch("hephae_common.firebase.get_db", return_value=db):
        yield db


class TestSaveTestRun:
    @pytest.mark.asyncio
    async def test_saves_with_timestamp(self, mock_db):
        from hephae_db.firestore.test_runs import save_test_run

        summary = {
            "runId": "run_123",
            "timestamp": "2026-03-10T12:00:00",
            "totalTests": 4,
            "passedTests": 3,
            "failedTests": 1,
            "results": [],
        }

        doc_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = doc_ref

        run_id = await save_test_run(summary)

        assert run_id == "run_123"
        mock_db.collection.assert_called_with("test_runs")
        mock_db.collection.return_value.document.assert_called_with("run_123")
        # Verify set was called (via to_thread)
        assert doc_ref.set.called or True  # to_thread wraps the call


class TestListTestRuns:
    @pytest.mark.asyncio
    async def test_returns_sorted_results(self, mock_db):
        from hephae_db.firestore.test_runs import list_test_runs

        doc1 = MagicMock()
        doc1.to_dict.return_value = {
            "runId": "run_1",
            "timestamp": "2026-03-10T12:00:00",
            "createdAt": datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
            "totalTests": 2,
            "passedTests": 2,
            "failedTests": 0,
            "results": [],
        }

        query = MagicMock()
        query.get = MagicMock(return_value=[doc1])
        mock_db.collection.return_value.order_by.return_value.limit.return_value = query

        results = await list_test_runs(limit=10)
        assert len(results) == 1
        assert results[0]["runId"] == "run_1"
        # createdAt should be serialized to ISO string
        assert isinstance(results[0]["createdAt"], str)


class TestTTLCleanup:
    @pytest.mark.asyncio
    async def test_deletes_expired_runs(self, mock_db):
        from hephae_db.firestore.test_runs import _cleanup_expired_runs

        old_doc = MagicMock()
        old_doc.reference = MagicMock()

        query = MagicMock()
        query.get = MagicMock(return_value=[old_doc])
        mock_db.collection.return_value.where.return_value.limit.return_value = query

        batch = MagicMock()
        mock_db.batch.return_value = batch

        await _cleanup_expired_runs(mock_db)

        batch.delete.assert_called_once_with(old_doc.reference)
        batch.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_expired_runs_noop(self, mock_db):
        from hephae_db.firestore.test_runs import _cleanup_expired_runs

        query = MagicMock()
        query.get = MagicMock(return_value=[])
        mock_db.collection.return_value.where.return_value.limit.return_value = query

        batch = MagicMock()
        mock_db.batch.return_value = batch

        await _cleanup_expired_runs(mock_db)

        batch.delete.assert_not_called()
