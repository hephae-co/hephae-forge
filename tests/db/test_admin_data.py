"""
Unit tests for backend/lib/admin_data.py

Covers: Firestore readers for zipcode_research and area_research collections.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from hephae_db.context.admin_data import get_zipcode_report, get_area_research_for_zip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_firestore_query(docs):
    """Create a mock Firestore query that returns the given docs."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_query = MagicMock()

    mock_db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.get.return_value = docs

    return mock_db


def _mock_doc(data):
    """Create a mock Firestore document."""
    doc = MagicMock()
    doc.to_dict.return_value = data
    return doc


# ---------------------------------------------------------------------------
# get_zipcode_report
# ---------------------------------------------------------------------------

class TestGetZipcodeReport:
    @pytest.mark.asyncio
    async def test_returns_none_for_empty_zip(self):
        result = await get_zipcode_report("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_none_zip(self):
        result = await get_zipcode_report(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_report_from_firestore(self):
        report = {"sections": {"demographics": {"population": 30000}}}
        doc = _mock_doc({"report": report, "zipCode": "07110"})
        mock_db = _mock_firestore_query([doc])

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_zipcode_report("07110")
            assert result == report

    @pytest.mark.asyncio
    async def test_returns_none_when_no_docs(self):
        mock_db = _mock_firestore_query([])

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_zipcode_report("99999")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("Firestore unavailable")

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_zipcode_report("07110")
            assert result is None


# ---------------------------------------------------------------------------
# get_area_research_for_zip
# ---------------------------------------------------------------------------

class TestGetAreaResearch:
    @pytest.mark.asyncio
    async def test_returns_none_for_empty_zip(self):
        result = await get_area_research_for_zip("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_summary_from_firestore(self):
        summary = {"marketOpportunity": "High growth", "competitiveLandscape": "Low saturation"}
        doc = _mock_doc({"summary": summary, "phase": "completed"})
        mock_db = _mock_firestore_query([doc])

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_area_research_for_zip("07110")
            assert result == summary

    @pytest.mark.asyncio
    async def test_returns_none_when_no_docs(self):
        mock_db = _mock_firestore_query([])

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_area_research_for_zip("99999")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("Firestore down")

        with patch("hephae_common.firebase.db", mock_db):
            result = await get_area_research_for_zip("07110")
            assert result is None
