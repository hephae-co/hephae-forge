"""Unit tests for public pulse endpoints.

GET /api/pulse/zipcode/{zip_code}
POST /api/pulse/zipcode-interest
GET /api/pulse/industry/{industry_key}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    from hephae_api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reg_doc(exists: bool = True, status: str = "active", **extra):
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = {
        "status": status,
        "city": "Nutley",
        "state": "NJ",
        "lastPulseAt": None,
        "lastPulseHeadline": "Busy week ahead",
        "pulseCount": 5,
        **extra,
    }
    return doc


def _make_db(doc=None):
    db = MagicMock()
    db.collection.return_value.document.return_value.get.return_value = doc or _make_reg_doc()
    return db


# ---------------------------------------------------------------------------
# Tests: GET /api/pulse/zipcode/{zip_code}
# ---------------------------------------------------------------------------

class TestGetZipcodeCoverage:
    @pytest.mark.asyncio
    async def test_returns_ultralocal_true_for_active_zip(self, client):
        doc = _make_reg_doc(exists=True, status="active")
        db = _make_db(doc)

        with (
            patch("hephae_api.routers.web.pulse_public.get_db", return_value=db),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=3),
        ):
            res = await client.get("/api/pulse/zipcode/07110")

        assert res.status_code == 200
        data = res.json()
        assert data["ultralocal"] is True
        assert data["city"] == "Nutley"
        assert data["state"] == "NJ"
        assert data["interestCount"] == 3

    @pytest.mark.asyncio
    async def test_returns_ultralocal_false_for_paused_zip(self, client):
        doc = _make_reg_doc(exists=True, status="paused")
        db = _make_db(doc)

        with (
            patch("hephae_api.routers.web.pulse_public.get_db", return_value=db),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=0),
        ):
            res = await client.get("/api/pulse/zipcode/07110")

        assert res.status_code == 200
        assert res.json()["ultralocal"] is False

    @pytest.mark.asyncio
    async def test_returns_ultralocal_false_when_not_registered(self, client):
        doc = MagicMock()
        doc.exists = False
        db = _make_db(doc)

        with (
            patch("hephae_api.routers.web.pulse_public.get_db", return_value=db),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=1),
        ):
            res = await client.get("/api/pulse/zipcode/99999")

        assert res.status_code == 200
        data = res.json()
        assert data["ultralocal"] is False
        assert data["city"] is None
        assert data["interestCount"] == 1

    @pytest.mark.asyncio
    async def test_400_for_invalid_zip_format(self, client):
        res = await client.get("/api/pulse/zipcode/abc")
        assert res.status_code == 400
        assert "invalid" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_400_for_short_zip(self, client):
        res = await client.get("/api/pulse/zipcode/1234")
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_pulse_count_and_headline(self, client):
        doc = _make_reg_doc(exists=True, status="active")
        db = _make_db(doc)

        with (
            patch("hephae_api.routers.web.pulse_public.get_db", return_value=db),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=0),
        ):
            res = await client.get("/api/pulse/zipcode/07110")

        data = res.json()
        assert data["pulseCount"] == 5
        assert data["latestHeadline"] == "Busy week ahead"


# ---------------------------------------------------------------------------
# Tests: POST /api/pulse/zipcode-interest
# ---------------------------------------------------------------------------

class TestSubmitZipcodeInterest:
    @pytest.mark.asyncio
    async def test_records_interest_and_returns_200(self, client):
        with (
            patch("hephae_db.firestore.zipcode_interest.save_zipcode_interest", new_callable=AsyncMock, return_value="interest-123"),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=1),
            patch("hephae_api.routers.web.pulse_public._resolve_geo", new_callable=AsyncMock, return_value=("Nutley", "NJ")),
        ):
            res = await client.post("/api/pulse/zipcode-interest", json={
                "zipCode": "07110",
                "businessType": "Restaurants",
                "email": "test@example.com",
            })

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["zipCode"] == "07110"
        assert data["interestCount"] == 1

    @pytest.mark.asyncio
    async def test_400_for_invalid_zip(self, client):
        res = await client.post("/api/pulse/zipcode-interest", json={"zipCode": "invalid"})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_optional_fields_not_required(self, client):
        with (
            patch("hephae_db.firestore.zipcode_interest.save_zipcode_interest", new_callable=AsyncMock, return_value="int-456"),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=0),
            patch("hephae_api.routers.web.pulse_public._resolve_geo", new_callable=AsyncMock, return_value=(None, None)),
        ):
            res = await client.post("/api/pulse/zipcode-interest", json={"zipCode": "10001"})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_city_state_in_response(self, client):
        with (
            patch("hephae_db.firestore.zipcode_interest.save_zipcode_interest", new_callable=AsyncMock, return_value="int-789"),
            patch("hephae_api.routers.web.pulse_public._get_interest_count", new_callable=AsyncMock, return_value=2),
            patch("hephae_api.routers.web.pulse_public._resolve_geo", new_callable=AsyncMock, return_value=("Manhattan", "NY")),
        ):
            res = await client.post("/api/pulse/zipcode-interest", json={"zipCode": "10001"})
        data = res.json()
        assert data["city"] == "Manhattan"
        assert data["state"] == "NY"


# ---------------------------------------------------------------------------
# Tests: GET /api/pulse/industry/{industry_key}
# ---------------------------------------------------------------------------

SAMPLE_INDUSTRY_PULSE = {
    "id": "restaurants-2026-W13",
    "industryKey": "restaurants",
    "weekOf": "2026-W13",
    "trendSummary": "Food costs rising 3.2% YoY",
    "nationalPlaybooks": [
        {"name": "Reduce Portion", "category": "cost", "play": "Reduce portion size by 5%"},
    ],
    "nationalImpact": {"cpi_food_away_from_home": 3.2, "beef_cost_change_pct": 5.1},
    "signalsUsed": ["bls_cpi", "usda_prices"],
}


class TestGetIndustryPulseSummary:
    @pytest.mark.asyncio
    async def test_returns_found_true_when_pulse_exists(self, client):
        with patch("hephae_db.firestore.industry_pulse.get_latest_industry_pulse", new_callable=AsyncMock, return_value=SAMPLE_INDUSTRY_PULSE):
            res = await client.get("/api/pulse/industry/restaurants")

        assert res.status_code == 200
        data = res.json()
        assert data["found"] is True
        assert data["industryKey"] == "restaurants"
        assert data["weekOf"] == "2026-W13"
        assert "trendSummary" in data
        assert len(data["playbooks"]) == 1

    @pytest.mark.asyncio
    async def test_returns_404_when_no_pulse(self, client):
        with patch("hephae_db.firestore.industry_pulse.get_latest_industry_pulse", new_callable=AsyncMock, return_value=None):
            res = await client.get("/api/pulse/industry/unknown-industry")

        assert res.status_code == 404
        data = res.json()
        assert data["found"] is False

    @pytest.mark.asyncio
    async def test_includes_key_metrics_numerics_only(self, client):
        with patch("hephae_db.firestore.industry_pulse.get_latest_industry_pulse", new_callable=AsyncMock, return_value=SAMPLE_INDUSTRY_PULSE):
            res = await client.get("/api/pulse/industry/restaurants")

        data = res.json()
        assert "keyMetrics" in data
        # Both values are nonzero numbers
        assert data["keyMetrics"]["cpi_food_away_from_home"] == 3.2
        assert data["keyMetrics"]["beef_cost_change_pct"] == 5.1

    @pytest.mark.asyncio
    async def test_includes_signals_used(self, client):
        with patch("hephae_db.firestore.industry_pulse.get_latest_industry_pulse", new_callable=AsyncMock, return_value=SAMPLE_INDUSTRY_PULSE):
            res = await client.get("/api/pulse/industry/restaurants")

        data = res.json()
        assert "bls_cpi" in data["signalsUsed"]

    @pytest.mark.asyncio
    async def test_industry_key_lowercased(self, client):
        """Industry key is normalized to lowercase."""
        with patch("hephae_db.firestore.industry_pulse.get_latest_industry_pulse", new_callable=AsyncMock, return_value=SAMPLE_INDUSTRY_PULSE) as mock_get:
            res = await client.get("/api/pulse/industry/Restaurants")

        assert res.status_code == 200
        # Should have been called with lowercase
        mock_get.assert_called_with("restaurants")
