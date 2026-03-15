"""Unit tests for discovery_jobs Firestore CRUD.

Tests cover:
- _deserialize: Firestore timestamp conversion
- create_discovery_job: correct document structure, default settings
- DiscoveryJobConfig.from_firestore: minimal and full data
- cancel_job: only cancels pending, returns False for non-pending
- complete_job: sets status + completedAt
"""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock


class TestDeserialize:
    def test_adds_id_field(self):
        from hephae_db.firestore.discovery_jobs import _deserialize
        result = _deserialize({"name": "Test", "status": "pending"}, "job-123")
        assert result["id"] == "job-123"

    def test_leaves_non_timestamp_fields_unchanged(self):
        from hephae_db.firestore.discovery_jobs import _deserialize
        data = {"name": "Job", "status": "running", "createdAt": None}
        result = _deserialize(data, "job-1")
        assert result["createdAt"] is None

    def test_converts_firestore_timestamp(self):
        from hephae_db.firestore.discovery_jobs import _deserialize
        mock_ts = MagicMock()
        mock_ts.seconds = 1_700_000_000
        mock_ts.nanoseconds = 0
        data = {"name": "Job", "status": "pending", "createdAt": mock_ts}
        result = _deserialize(data, "job-1")
        assert isinstance(result["createdAt"], datetime)


class TestCreateDiscoveryJob:
    @pytest.mark.asyncio
    async def test_creates_with_correct_structure(self):
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new-job-id"
        mock_doc_ref.set = MagicMock()

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        targets = [{"zipCode": "07110", "businessTypes": ["restaurant"]}]

        with patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import create_discovery_job
            job_id = await create_discovery_job("Test Job", targets, "admin@hephae.co")

        assert job_id == "new-job-id"
        called_data = mock_thread.call_args[0][1]  # second arg to to_thread is the data dict
        assert called_data["status"] == "pending"
        assert called_data["targets"] == targets
        assert called_data["notifyEmail"] == "admin@hephae.co"
        assert "progress" in called_data
        assert called_data["progress"]["totalZips"] == 1

    @pytest.mark.asyncio
    async def test_uses_default_settings_when_none_provided(self):
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "job-1"
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        with patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import create_discovery_job
            await create_discovery_job("Job", [{"zipCode": "10001"}])

        data = mock_thread.call_args[0][1]
        assert data["settings"]["freshnessDiscoveryDays"] == 30
        assert data["settings"]["freshnessAnalysisDays"] == 7
        assert data["settings"]["rateLimitSeconds"] == 3

    @pytest.mark.asyncio
    async def test_uses_provided_settings(self):
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "job-2"
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref

        custom_settings = {"freshnessDiscoveryDays": 7, "freshnessAnalysisDays": 1, "rateLimitSeconds": 5}

        with patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import create_discovery_job
            await create_discovery_job("Job", [{"zipCode": "10001"}], settings=custom_settings)

        data = mock_thread.call_args[0][1]
        assert data["settings"]["freshnessDiscoveryDays"] == 7


class TestDiscoveryJobConfig:
    """DiscoveryJobConfig.from_firestore parses Firestore data correctly."""

    def test_minimal_data(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryJobConfig
        data = {
            "id": "job-1",
            "targets": [{"zipCode": "07110"}],
        }
        config = DiscoveryJobConfig.from_firestore(data)
        assert config.id == "job-1"
        assert config.name == "Unnamed Job"
        assert config.notify_email == "admin@hephae.co"
        assert len(config.targets) == 1
        assert config.targets[0].zipCode == "07110"
        assert config.targets[0].businessTypes == []

    def test_full_data(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryJobConfig
        data = {
            "id": "job-2",
            "name": "Nutley NJ",
            "targets": [
                {"zipCode": "07110", "businessTypes": ["restaurant", "cafe"]},
                {"zipCode": "07111"},
            ],
            "notifyEmail": "ops@company.com",
            "settings": {
                "freshnessDiscoveryDays": 14,
                "freshnessAnalysisDays": 3,
                "rateLimitSeconds": 5,
            },
        }
        config = DiscoveryJobConfig.from_firestore(data)
        assert config.name == "Nutley NJ"
        assert config.notify_email == "ops@company.com"
        assert config.settings.freshnessDiscoveryDays == 14
        assert config.settings.freshnessAnalysisDays == 3
        assert config.settings.rateLimitSeconds == 5
        assert len(config.targets) == 2
        assert config.targets[0].businessTypes == ["restaurant", "cafe"]
        assert config.targets[1].zipCode == "07111"

    def test_missing_settings_uses_defaults(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryJobConfig
        data = {"id": "job-3", "targets": []}
        config = DiscoveryJobConfig.from_firestore(data)
        assert config.settings.freshnessDiscoveryDays == 30
        assert config.settings.rateLimitSeconds == 3

    def test_empty_settings_dict_uses_defaults(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryJobConfig
        data = {"id": "job-4", "targets": [], "settings": {}}
        config = DiscoveryJobConfig.from_firestore(data)
        assert config.settings.freshnessDiscoveryDays == 30


class TestCancelJob:
    @pytest.mark.asyncio
    async def test_cancels_pending_job(self):
        pending_job = {"id": "job-1", "status": "pending"}
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.update = MagicMock()

        with patch("hephae_db.firestore.discovery_jobs.get_discovery_job",
                   new_callable=AsyncMock, return_value=pending_job), \
             patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import cancel_job
            result = await cancel_job("job-1")

        assert result is True
        # Verify the update was called with CANCELLED status
        update_data = mock_thread.call_args[0][1]
        assert update_data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_returns_false_for_running_job(self):
        running_job = {"id": "job-1", "status": "running"}
        with patch("hephae_db.firestore.discovery_jobs.get_discovery_job",
                   new_callable=AsyncMock, return_value=running_job):
            from hephae_db.firestore.discovery_jobs import cancel_job
            result = await cancel_job("job-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_completed_job(self):
        completed = {"id": "job-1", "status": "completed"}
        with patch("hephae_db.firestore.discovery_jobs.get_discovery_job",
                   new_callable=AsyncMock, return_value=completed):
            from hephae_db.firestore.discovery_jobs import cancel_job
            result = await cancel_job("job-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_job(self):
        with patch("hephae_db.firestore.discovery_jobs.get_discovery_job",
                   new_callable=AsyncMock, return_value=None):
            from hephae_db.firestore.discovery_jobs import cancel_job
            result = await cancel_job("no-such-job")
        assert result is False


class TestCompleteJob:
    @pytest.mark.asyncio
    async def test_sets_completed_status(self):
        mock_db = MagicMock()
        with patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import complete_job
            await complete_job("job-1")

        update_data = mock_thread.call_args[0][1]
        assert update_data["status"] == "completed"
        assert "completedAt" in update_data

    @pytest.mark.asyncio
    async def test_sets_failed_status_with_error(self):
        mock_db = MagicMock()
        with patch("hephae_db.firestore.discovery_jobs.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            from hephae_db.firestore.discovery_jobs import complete_job, STATUS_FAILED
            await complete_job("job-1", status=STATUS_FAILED, error="Timeout after 8h")

        update_data = mock_thread.call_args[0][1]
        assert update_data["status"] == "failed"
        assert update_data["error"] == "Timeout after 8h"
