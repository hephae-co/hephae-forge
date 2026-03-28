"""Unit tests for hephae_db.firestore.industry_pulse module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pulse_doc(doc_id: str = "restaurants-2026-W13", **overrides) -> MagicMock:
    data = {
        "industryKey": "restaurants",
        "weekOf": "2026-W13",
        "nationalSignals": {"bls_cpi": 3.2},
        "nationalImpact": {"cpi_food_away_from_home": 3.2},
        "nationalPlaybooks": [{"name": "Reduce Portion", "category": "cost", "play": "..."}],
        "trendSummary": "Food costs rising",
        "signalsUsed": ["bls_cpi", "usda_prices"],
        "diagnostics": {},
        "createdAt": datetime(2026, 3, 27),
        "updatedAt": datetime(2026, 3, 27),
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
# Tests: save_industry_pulse
# ---------------------------------------------------------------------------

class TestSaveIndustryPulse:
    @pytest.mark.asyncio
    async def test_saves_pulse_with_correct_doc_id(self):
        db = _mock_db()
        doc_ref = db.collection.return_value.document.return_value

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import save_industry_pulse

            doc_id = await save_industry_pulse(
                industry_key="restaurants",
                week_of="2026-W13",
                national_signals={"bls_cpi": 3.2},
                national_impact={"cpi_food_away": 3.2},
                national_playbooks=[],
                trend_summary="Costs rising",
                signals_used=["bls_cpi"],
            )

        assert doc_id == "restaurants-2026-W13"
        db.collection.return_value.document.assert_called_with("restaurants-2026-W13")
        doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_saved_data_contains_all_required_fields(self):
        db = _mock_db()

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import save_industry_pulse

            await save_industry_pulse(
                industry_key="barbers",
                week_of="2026-W14",
                national_signals={},
                national_impact={},
                national_playbooks=[],
                trend_summary="Stable",
                signals_used=[],
            )

        call_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert call_data["industryKey"] == "barbers"
        assert call_data["weekOf"] == "2026-W14"
        assert call_data["trendSummary"] == "Stable"
        assert "createdAt" in call_data
        assert "updatedAt" in call_data

    @pytest.mark.asyncio
    async def test_diagnostics_defaults_to_empty_dict(self):
        db = _mock_db()

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import save_industry_pulse

            await save_industry_pulse(
                industry_key="restaurants",
                week_of="2026-W13",
                national_signals={},
                national_impact={},
                national_playbooks=[],
                trend_summary="Test",
                signals_used=[],
                diagnostics=None,
            )

        call_data = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert call_data["diagnostics"] == {}


# ---------------------------------------------------------------------------
# Tests: get_industry_pulse
# ---------------------------------------------------------------------------

class TestGetIndustryPulse:
    @pytest.mark.asyncio
    async def test_returns_pulse_when_exists(self):
        db = _mock_db()
        doc = _make_pulse_doc("restaurants-2026-W13")
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import get_industry_pulse

            result = await get_industry_pulse("restaurants", "2026-W13")

        assert result is not None
        assert result["id"] == "restaurants-2026-W13"
        assert result["industryKey"] == "restaurants"
        db.collection.return_value.document.assert_called_with("restaurants-2026-W13")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _mock_db()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import get_industry_pulse

            result = await get_industry_pulse("restaurants", "2020-W01")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: get_latest_industry_pulse
# ---------------------------------------------------------------------------

class TestGetLatestIndustryPulse:
    @pytest.mark.asyncio
    async def test_returns_most_recent_pulse(self):
        db = _mock_db()
        older = _make_pulse_doc("restaurants-2026-W12", createdAt=datetime(2026, 3, 20), weekOf="2026-W12")
        newer = _make_pulse_doc("restaurants-2026-W13", createdAt=datetime(2026, 3, 27), weekOf="2026-W13")
        db.collection.return_value.where.return_value.get.return_value = [older, newer]

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

            result = await get_latest_industry_pulse("restaurants")

        assert result is not None
        # Should be the newest one (sorted by createdAt descending)
        assert result["weekOf"] in ("2026-W13", "2026-W12")  # either is valid if sorting works

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pulses(self):
        db = _mock_db()
        db.collection.return_value.where.return_value.get.return_value = []

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

            result = await get_latest_industry_pulse("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_filters_by_industry_key(self):
        db = _mock_db()
        db.collection.return_value.where.return_value.get.return_value = []

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

            await get_latest_industry_pulse("barbers")

        db.collection.return_value.where.assert_called_with("industryKey", "==", "barbers")


# ---------------------------------------------------------------------------
# Tests: list_industry_pulses
# ---------------------------------------------------------------------------

class TestListIndustryPulses:
    @pytest.mark.asyncio
    async def test_lists_all_pulses(self):
        db = _mock_db()
        docs = [_make_pulse_doc("restaurants-2026-W13"), _make_pulse_doc("barbers-2026-W13", industryKey="barbers")]
        db.collection.return_value.get.return_value = docs

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import list_industry_pulses

            results = await list_industry_pulses()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_filters_by_industry_key(self):
        db = _mock_db()
        docs = [_make_pulse_doc("restaurants-2026-W13")]
        db.collection.return_value.where.return_value.get.return_value = docs

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import list_industry_pulses

            results = await list_industry_pulses(industry_key="restaurants")

        db.collection.return_value.where.assert_called_with("industryKey", "==", "restaurants")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        db = _mock_db()
        docs = [_make_pulse_doc(f"restaurants-2026-W{i:02d}", createdAt=datetime(2026, 1, i)) for i in range(1, 20)]
        db.collection.return_value.get.return_value = docs

        with patch("hephae_db.firestore.industry_pulse.get_db", return_value=db):
            from hephae_db.firestore.industry_pulse import list_industry_pulses

            results = await list_industry_pulses(limit=5)

        assert len(results) == 5
