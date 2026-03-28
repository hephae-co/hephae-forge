"""Unit tests for hephae_db.firestore.pulse_jobs module."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job_doc(job_id: str = "job-001", status: str = "QUEUED", **overrides) -> MagicMock:
    data = {
        "zipCode": "07110",
        "businessType": "Restaurants",
        "weekOf": "2026-W13",
        "force": False,
        "status": status,
        "createdAt": datetime(2026, 3, 27, 6, 0),
        "startedAt": None,
        "completedAt": None,
        "result": None,
        "error": None,
        **overrides,
    }
    doc = MagicMock()
    doc.id = job_id
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _mock_db():
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests: create_pulse_job
# ---------------------------------------------------------------------------

class TestCreatePulseJob:
    @pytest.mark.asyncio
    async def test_creates_job_with_queued_status(self):
        db = _mock_db()
        doc_ref = MagicMock()
        doc_ref.id = "new-job-123"
        db.collection.return_value.document.return_value = doc_ref

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import create_pulse_job

            job_id = await create_pulse_job(
                zip_code="07110",
                business_type="Restaurants",
                week_of="2026-W13",
            )

        assert job_id == "new-job-123"
        doc_ref.set.assert_called_once()
        call_data = doc_ref.set.call_args[0][0]
        assert call_data["status"] == "QUEUED"
        assert call_data["zipCode"] == "07110"
        assert call_data["businessType"] == "Restaurants"
        assert call_data["weekOf"] == "2026-W13"

    @pytest.mark.asyncio
    async def test_creates_job_in_test_mode(self):
        db = _mock_db()
        doc_ref = MagicMock()
        doc_ref.id = "test-job-456"
        db.collection.return_value.document.return_value = doc_ref

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import create_pulse_job

            await create_pulse_job("07110", "Restaurants", "2026-W13", test_mode=True)

        call_data = doc_ref.set.call_args[0][0]
        assert call_data.get("testMode") is True
        assert "expireAt" in call_data

    @pytest.mark.asyncio
    async def test_force_flag_stored(self):
        db = _mock_db()
        doc_ref = MagicMock()
        doc_ref.id = "force-job-789"
        db.collection.return_value.document.return_value = doc_ref

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import create_pulse_job

            await create_pulse_job("07110", "Restaurants", "2026-W13", force=True)

        call_data = doc_ref.set.call_args[0][0]
        assert call_data["force"] is True


# ---------------------------------------------------------------------------
# Tests: get_pulse_job
# ---------------------------------------------------------------------------

class TestGetPulseJob:
    @pytest.mark.asyncio
    async def test_returns_job_when_exists(self):
        db = _mock_db()
        doc = _make_job_doc("job-001")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import get_pulse_job

            result = await get_pulse_job("job-001")

        assert result is not None
        assert result["id"] == "job-001"
        assert result["zipCode"] == "07110"
        assert result["status"] == "QUEUED"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import get_pulse_job

            result = await get_pulse_job("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_auto_fails_timed_out_running_job(self):
        """RUNNING job past timeoutAt should be marked FAILED."""
        db = _mock_db()
        past_timeout = datetime.utcnow() - timedelta(minutes=1)
        doc = _make_job_doc("job-timeout", status="RUNNING", timeoutAt=past_timeout)
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import get_pulse_job

            result = await get_pulse_job("job-timeout")

        # Job should have been marked FAILED
        assert result["status"] == "FAILED"
        assert "timeout" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Tests: update_pulse_job
# ---------------------------------------------------------------------------

class TestUpdatePulseJob:
    @pytest.mark.asyncio
    async def test_updates_job_fields(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import update_pulse_job

            await update_pulse_job("job-001", {"status": "RUNNING", "startedAt": datetime.utcnow()})

        doc_ref.update.assert_called_once()
        call_data = doc_ref.update.call_args[0][0]
        assert call_data["status"] == "RUNNING"


# ---------------------------------------------------------------------------
# Tests: list_pulse_jobs
# ---------------------------------------------------------------------------

class TestListPulseJobs:
    @pytest.mark.asyncio
    async def test_returns_recent_jobs(self):
        db = _mock_db()
        docs = [_make_job_doc("job-1"), _make_job_doc("job-2")]
        db.collection.return_value.order_by.return_value.limit.return_value.get.return_value = docs

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import list_pulse_jobs

            results = await list_pulse_jobs(limit=20)

        assert len(results) == 2
        assert results[0]["id"] == "job-1"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_jobs(self):
        db = _mock_db()
        db.collection.return_value.order_by.return_value.limit.return_value.get.return_value = []

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import list_pulse_jobs

            results = await list_pulse_jobs()

        assert results == []

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self):
        db = _mock_db()

        with patch("hephae_db.firestore.pulse_jobs.get_db", return_value=db):
            from hephae_db.firestore.pulse_jobs import list_pulse_jobs

            await list_pulse_jobs(limit=5)

        db.collection.return_value.order_by.return_value.limit.assert_called_with(5)
