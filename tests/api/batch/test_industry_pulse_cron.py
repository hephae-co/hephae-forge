"""Unit tests for GET /api/cron/industry-pulse.

Covers: valid cron secret → 200, invalid → 401, missing → 401,
CRON_SECRET not set → allows through.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_industry(key: str = "restaurants", display_name: str = "Restaurants") -> dict:
    return {"industryKey": key, "displayName": display_name, "status": "active"}


SAMPLE_PULSE = {
    "id": "restaurants-2026-W13",
    "industryKey": "restaurants",
    "weekOf": "2026-W13",
    "trendSummary": "Food costs up 3.2%",
    "nationalPlaybooks": [],
    "signalsUsed": ["bls_cpi", "usda_prices"],
}


# ---------------------------------------------------------------------------
# Tests: Auth
# ---------------------------------------------------------------------------

class TestIndustryPulseCronAuth:
    @pytest.mark.asyncio
    async def test_valid_bearer_token_returns_200(self):
        """Valid Bearer token → 200."""
        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = "cron-token"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/industry-pulse",
                    headers={"Authorization": "Bearer cron-token"},
                )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """Wrong token → 401."""
        with patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = "cron-token"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/industry-pulse",
                    headers={"Authorization": "Bearer wrong"},
                )
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_returns_401(self):
        """No auth header → 401."""
        with patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = "cron-token"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/industry-pulse")
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_cron_secret_allows_through(self):
        """When CRON_SECRET is empty, all requests pass."""
        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/industry-pulse")
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_x_cron_secret_header_accepted(self):
        """X-Cron-Secret header is also accepted."""
        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = "cron-token"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/industry-pulse",
                    headers={"X-Cron-Secret": "cron-token"},
                )
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Behavior
# ---------------------------------------------------------------------------

class TestIndustryPulseCronBehavior:
    @pytest.mark.asyncio
    async def test_no_active_industries_returns_zero(self):
        """No active industries → generated=0."""
        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/industry-pulse")

        assert res.status_code == 200
        data = res.json()
        assert data["generated"] == 0

    @pytest.mark.asyncio
    async def test_generates_pulses_for_active_industries(self):
        """Active industries get pulses generated."""
        industry = _mock_industry("restaurants", "Restaurants")
        pulse_with_id = {**SAMPLE_PULSE, "id": "restaurants-2026-W13"}

        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[industry]),
            patch("hephae_db.firestore.registered_industries.update_last_industry_pulse", new_callable=AsyncMock),
            patch("hephae_api.workflows.orchestrators.industry_pulse.generate_industry_pulses_batch", new_callable=AsyncMock, return_value=[pulse_with_id]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/industry-pulse")

        assert res.status_code == 200
        data = res.json()
        assert data["generated"] == 1
        assert data["failed"] == 0
        assert len(data["results"]) == 1
        assert data["results"][0]["industryKey"] == "restaurants"

    @pytest.mark.asyncio
    async def test_marks_all_failed_on_batch_exception(self):
        """If batch generation raises, all industries marked failed."""
        industry = _mock_industry("restaurants", "Restaurants")

        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[industry]),
            patch("hephae_api.workflows.orchestrators.industry_pulse.generate_industry_pulses_batch", new_callable=AsyncMock, side_effect=RuntimeError("LLM error")),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/industry-pulse")

        assert res.status_code == 200
        data = res.json()
        assert data["generated"] == 0
        assert data["failed"] == 1
