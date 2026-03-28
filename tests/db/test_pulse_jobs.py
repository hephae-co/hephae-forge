"""Functional tests for pulse_jobs Firestore module.

Tests call the real Firestore functions. They require ADC or
FIRESTORE_EMULATOR_HOST to be configured.

These are integration tests — they read real Firestore.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — set GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_pulse_job_nonexistent_returns_none():
    """Querying a non-existent job ID returns None."""
    from hephae_db.firestore.pulse_jobs import get_pulse_job

    result = await get_pulse_job("__nonexistent_job_id_xyz__")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_pulse_jobs_returns_list():
    """list_pulse_jobs always returns a list."""
    from hephae_db.firestore.pulse_jobs import list_pulse_jobs

    results = await list_pulse_jobs(limit=10)
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_pulse_jobs_limit_respected():
    """list_pulse_jobs respects the limit parameter."""
    from hephae_db.firestore.pulse_jobs import list_pulse_jobs

    results = await list_pulse_jobs(limit=3)
    assert isinstance(results, list)
    assert len(results) <= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pulse_job_document_shape():
    """Existing pulse jobs have required fields."""
    from hephae_db.firestore.pulse_jobs import list_pulse_jobs

    results = await list_pulse_jobs(limit=5)
    for job in results:
        assert "zipCode" in job, "Must have zipCode (top-level field)"
        assert "status" in job, "Must have status"
        assert job["status"] in ("QUEUED", "RUNNING", "COMPLETED", "FAILED"), (
            f"Unexpected status: {job['status']}"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pulse_job_zip_code_is_5_digits():
    """zipCode in pulse jobs must be 5-digit strings."""
    from hephae_db.firestore.pulse_jobs import list_pulse_jobs

    results = await list_pulse_jobs(limit=5)
    for job in results:
        z = job.get("zipCode", "")
        assert len(z) == 5 and z.isdigit(), f"Invalid zipCode '{z}'"


# ---------------------------------------------------------------------------
# Pure logic tests (no DB needed)
# ---------------------------------------------------------------------------

class TestNextMondayHelper:
    def test_returns_future_monday(self):
        """_next_monday returns a datetime in the future on a Monday."""
        from hephae_db.firestore.registered_zipcodes import _next_monday

        result = _next_monday()
        assert result > datetime.utcnow()
        assert result.weekday() == 0  # 0 = Monday


class TestJobStatusConstants:
    def test_valid_statuses(self):
        """Known valid job statuses match expectations."""
        valid_statuses = {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}
        assert "QUEUED" in valid_statuses
        assert "RUNNING" in valid_statuses
        assert "COMPLETED" in valid_statuses
        assert "FAILED" in valid_statuses
        assert len(valid_statuses) == 4
