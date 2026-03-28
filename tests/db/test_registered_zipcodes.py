"""Unit tests for hephae_db.firestore.registered_zipcodes module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip_doc(zip_code: str = "07110", **overrides) -> MagicMock:
    data = {
        "zipCode": zip_code,
        "city": "Nutley",
        "state": "NJ",
        "county": "Essex",
        "status": "active",
        "onboardingStatus": "onboarding",
        "businessTypes": ["Restaurants"],
        "registeredAt": datetime(2026, 1, 1),
        "lastPulseAt": None,
        "lastPulseId": None,
        "lastPulseHeadline": "",
        "lastPulseInsightCount": 0,
        "pulseCount": 0,
        "onboardedAt": None,
        "nextScheduledAt": datetime(2026, 3, 10, 11, 0),
        "createdBy": "admin",
        **overrides,
    }
    doc = MagicMock()
    doc.id = zip_code
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _mock_db():
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests: register_zipcode
# ---------------------------------------------------------------------------

class TestRegisterZipcode:
    @pytest.mark.asyncio
    async def test_registers_new_zipcode(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import register_zipcode

            result = await register_zipcode("07110", "Nutley", "NJ", "Essex")

        doc_ref.set.assert_called_once()
        call_data = doc_ref.set.call_args[0][0]
        assert call_data["zipCode"] == "07110"
        assert call_data["city"] == "Nutley"
        assert call_data["state"] == "NJ"
        assert call_data["status"] == "active"
        assert call_data["pulseCount"] == 0
        assert result == "07110"

    @pytest.mark.asyncio
    async def test_sets_onboarding_status(self):
        db = _mock_db()
        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import register_zipcode
            await register_zipcode("10001", "New York", "NY", "New York")

        call_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert call_data["onboardingStatus"] == "onboarding"
        assert call_data["businessTypes"] == ["Restaurants"]


# ---------------------------------------------------------------------------
# Tests: get_registered_zipcode
# ---------------------------------------------------------------------------

class TestGetRegisteredZipcode:
    @pytest.mark.asyncio
    async def test_returns_zipcode_when_exists(self):
        db = _mock_db()
        doc = _make_zip_doc("07110")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import get_registered_zipcode

            result = await get_registered_zipcode("07110")

        assert result is not None
        assert result["zipCode"] == "07110"
        assert result["city"] == "Nutley"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import get_registered_zipcode

            result = await get_registered_zipcode("99999")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: list_registered_zipcodes
# ---------------------------------------------------------------------------

class TestListRegisteredZipcodes:
    @pytest.mark.asyncio
    async def test_returns_all_zipcodes(self):
        db = _mock_db()
        docs = [_make_zip_doc("07110"), _make_zip_doc("10001", city="New York", state="NY")]
        db.collection.return_value.order_by.return_value.get.return_value = docs

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

            results = await list_registered_zipcodes()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        db = _mock_db()
        docs = [_make_zip_doc("07110")]
        db.collection.return_value.order_by.return_value.where.return_value.get.return_value = docs

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

            results = await list_registered_zipcodes(status="active")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_when_none(self):
        db = _mock_db()
        db.collection.return_value.order_by.return_value.get.return_value = []

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

            results = await list_registered_zipcodes()

        assert results == []


# ---------------------------------------------------------------------------
# Tests: unregister_zipcode
# ---------------------------------------------------------------------------

class TestUnregisterZipcode:
    @pytest.mark.asyncio
    async def test_deletes_document(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import unregister_zipcode

            await unregister_zipcode("07110")

        doc_ref.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: pause_zipcode / resume_zipcode
# ---------------------------------------------------------------------------

class TestPauseResumeZipcode:
    @pytest.mark.asyncio
    async def test_pause_sets_paused_status(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import pause_zipcode

            await pause_zipcode("07110")

        doc_ref.update.assert_called_with({"status": "paused"})

    @pytest.mark.asyncio
    async def test_resume_sets_active_status(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import resume_zipcode

            await resume_zipcode("07110")

        call_data = doc_ref.update.call_args[0][0]
        assert call_data["status"] == "active"
        assert "nextScheduledAt" in call_data


# ---------------------------------------------------------------------------
# Tests: approve_zipcode
# ---------------------------------------------------------------------------

class TestApproveZipcode:
    @pytest.mark.asyncio
    async def test_sets_onboarded_status(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import approve_zipcode

            await approve_zipcode("07110")

        call_data = doc_ref.update.call_args[0][0]
        assert call_data["onboardingStatus"] == "onboarded"
        assert "onboardedAt" in call_data


# ---------------------------------------------------------------------------
# Tests: update_last_pulse
# ---------------------------------------------------------------------------

class TestUpdateLastPulse:
    @pytest.mark.asyncio
    async def test_updates_pulse_tracking_fields(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_zipcodes.get_db", return_value=db):
            from hephae_db.firestore.registered_zipcodes import update_last_pulse

            await update_last_pulse("07110", "pulse-123", headline="Big week", insight_count=5)

        call_data = doc_ref.update.call_args[0][0]
        assert call_data["lastPulseId"] == "pulse-123"
        assert call_data["lastPulseHeadline"] == "Big week"
        assert call_data["lastPulseInsightCount"] == 5
        assert "lastPulseAt" in call_data
        assert "nextScheduledAt" in call_data


# ---------------------------------------------------------------------------
# Tests: _next_monday helper
# ---------------------------------------------------------------------------

class TestNextMonday:
    def test_returns_future_monday(self):
        from hephae_db.firestore.registered_zipcodes import _next_monday

        result = _next_monday()
        assert result > datetime.utcnow()
        assert result.weekday() == 0  # Monday

    def test_returns_correct_hour(self):
        from hephae_db.firestore.registered_zipcodes import _next_monday

        result = _next_monday()
        assert result.hour == 11  # 11:00 UTC = 6:00 ET
