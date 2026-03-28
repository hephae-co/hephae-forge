"""Unit tests for hephae_db.firestore.tech_intelligence module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ti_doc(doc_id: str = "barber-2026-W12", **overrides) -> MagicMock:
    vertical, week_of = doc_id.rsplit("-", 2)[0], "-".join(doc_id.rsplit("-", 2)[1:])
    data = {
        "vertical": vertical,
        "weekOf": week_of,
        "generatedAt": datetime(2026, 3, 20),
        "techStack": ["Square POS", "Toast"],
        "emergingTrends": ["Online booking"],
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
# Tests: get_tech_intelligence
# ---------------------------------------------------------------------------

class TestGetTechIntelligence:
    @pytest.mark.asyncio
    async def test_returns_profile_when_exists(self):
        db = _mock_db()
        doc = _make_ti_doc("barber-2026-W12")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import get_tech_intelligence

            result = await get_tech_intelligence("barber", "2026-W12")

        assert result is not None
        assert result["id"] == "barber-2026-W12"
        assert result["vertical"] == "barber"
        db.collection.return_value.document.assert_called_with("barber-2026-W12")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import get_tech_intelligence

            result = await get_tech_intelligence("unknown", "2026-W01")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: save_tech_intelligence
# ---------------------------------------------------------------------------

class TestSaveTechIntelligence:
    @pytest.mark.asyncio
    async def test_saves_profile_with_correct_doc_id(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import save_tech_intelligence

            doc_id = await save_tech_intelligence(
                vertical="barber",
                week_of="2026-W12",
                profile={"techStack": ["Square POS"], "emergingTrends": []},
            )

        assert doc_id == "barber-2026-W12"
        db.collection.return_value.document.assert_called_with("barber-2026-W12")
        doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_includes_vertical_and_week_in_saved_data(self):
        db = _mock_db()

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import save_tech_intelligence

            await save_tech_intelligence("restaurants", "2026-W13", {"someField": "value"})

        call_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert call_data["vertical"] == "restaurants"
        assert call_data["weekOf"] == "2026-W13"
        assert call_data["someField"] == "value"
        assert "generatedAt" in call_data


# ---------------------------------------------------------------------------
# Tests: list_tech_intelligence
# ---------------------------------------------------------------------------

class TestListTechIntelligence:
    @pytest.mark.asyncio
    async def test_lists_all_profiles(self):
        db = _mock_db()
        docs = [
            _make_ti_doc("barber-2026-W12"),
            _make_ti_doc("barber-2026-W11", vertical="barber", weekOf="2026-W11"),
        ]
        db.collection.return_value.get.return_value = docs

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import list_tech_intelligence

            results = await list_tech_intelligence()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_filters_by_vertical(self):
        db = _mock_db()
        docs = [_make_ti_doc("barber-2026-W12")]
        db.collection.return_value.where.return_value.get.return_value = docs

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import list_tech_intelligence

            results = await list_tech_intelligence(vertical="barber")

        db.collection.return_value.where.assert_called_with("vertical", "==", "barber")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        db = _mock_db()
        docs = [_make_ti_doc(f"barber-2026-W{i:02d}", generatedAt=datetime(2026, 1, i)) for i in range(1, 16)]
        db.collection.return_value.get.return_value = docs

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import list_tech_intelligence

            results = await list_tech_intelligence(limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_returns_empty_when_none(self):
        db = _mock_db()
        db.collection.return_value.get.return_value = []

        with patch("hephae_db.firestore.tech_intelligence.get_db", return_value=db):
            from hephae_db.firestore.tech_intelligence import list_tech_intelligence

            results = await list_tech_intelligence()

        assert results == []
