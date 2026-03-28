"""Unit tests for hephae_db.firestore.registered_industries module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_industry_doc(doc_id: str = "restaurants", **overrides) -> MagicMock:
    data = {
        "industryKey": doc_id,
        "displayName": "Restaurants",
        "status": "active",
        "registeredAt": datetime(2026, 1, 1),
        "lastPulseAt": None,
        "lastPulseId": None,
        "pulseCount": 0,
        "createdBy": "admin",
        **overrides,
    }
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _mock_db():
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests: register_industry
# ---------------------------------------------------------------------------

class TestRegisterIndustry:
    @pytest.mark.asyncio
    async def test_registers_industry_successfully(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import register_industry

            result = await register_industry(
                industry_key="restaurants",
                display_name="Restaurants",
                created_by="admin",
            )

        doc_ref.set.assert_called_once()
        call_data = doc_ref.set.call_args[0][0]
        assert call_data["industryKey"] == "restaurants"
        assert call_data["displayName"] == "Restaurants"
        assert call_data["status"] == "active"
        assert call_data["pulseCount"] == 0
        assert result["id"] == "restaurants"

    @pytest.mark.asyncio
    async def test_registers_with_notes(self):
        db = _mock_db()

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import register_industry

            result = await register_industry(
                industry_key="barbers",
                display_name="Barbershops",
                notes="Focus on NYC market",
            )

        call_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert call_data["notes"] == "Focus on NYC market"


# ---------------------------------------------------------------------------
# Tests: get_registered_industry
# ---------------------------------------------------------------------------

class TestGetRegisteredIndustry:
    @pytest.mark.asyncio
    async def test_returns_industry_when_exists(self):
        db = _mock_db()
        doc = _make_industry_doc("restaurants")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import get_registered_industry

            result = await get_registered_industry("restaurants")

        assert result is not None
        assert result["id"] == "restaurants"
        assert result["displayName"] == "Restaurants"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import get_registered_industry

            result = await get_registered_industry("nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: list_registered_industries
# ---------------------------------------------------------------------------

class TestListRegisteredIndustries:
    @pytest.mark.asyncio
    async def test_returns_all_industries(self):
        db = _mock_db()
        docs = [_make_industry_doc("restaurants"), _make_industry_doc("barbers", displayName="Barbershops")]
        db.collection.return_value.get.return_value = docs

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import list_registered_industries

            results = await list_registered_industries()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        db = _mock_db()
        docs = [_make_industry_doc("restaurants")]
        db.collection.return_value.where.return_value.get.return_value = docs

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import list_registered_industries

            results = await list_registered_industries(status="active")

        db.collection.return_value.where.assert_called_with("status", "==", "active")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self):
        db = _mock_db()
        db.collection.return_value.get.return_value = []

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import list_registered_industries

            results = await list_registered_industries()

        assert results == []


# ---------------------------------------------------------------------------
# Tests: update_industry
# ---------------------------------------------------------------------------

class TestUpdateIndustry:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        db = _mock_db()
        doc = _make_industry_doc("restaurants", status="paused")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import update_industry

            result = await update_industry("restaurants", {"status": "paused"})

        db.collection.return_value.document.return_value.update.assert_called_once()
        assert result["id"] == "restaurants"


# ---------------------------------------------------------------------------
# Tests: unregister_industry
# ---------------------------------------------------------------------------

class TestUnregisterIndustry:
    @pytest.mark.asyncio
    async def test_deletes_document(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import unregister_industry

            await unregister_industry("restaurants")

        doc_ref.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: pause/resume
# ---------------------------------------------------------------------------

class TestPauseResumeIndustry:
    @pytest.mark.asyncio
    async def test_pause_sets_status_paused(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import pause_industry

            await pause_industry("restaurants")

        doc_ref.update.assert_called_with({"status": "paused"})

    @pytest.mark.asyncio
    async def test_resume_sets_status_active(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.registered_industries.get_db", return_value=db):
            from hephae_db.firestore.registered_industries import resume_industry

            await resume_industry("restaurants")

        doc_ref.update.assert_called_with({"status": "active"})
