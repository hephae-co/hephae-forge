"""Shared cron auth tests covering all cron routes.

Tests: weekly-pulse, industry-pulse, reference-harvest.
Each route:
- Valid Bearer token → proceeds (mock the handler)
- Invalid Bearer token → 401
- Missing auth header → 401
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


CRON_TOKEN = "test-cron-secret"


# ---------------------------------------------------------------------------
# Parametrized test helper
# ---------------------------------------------------------------------------

async def _call_cron(route: str, token: str | None = None) -> int:
    from hephae_api.main import app
    transport = ASGITransport(app=app)
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(route, headers=headers)
    return res.status_code


# ---------------------------------------------------------------------------
# Tests: weekly-pulse
# ---------------------------------------------------------------------------

class TestWeeklyPulseCronAuth:
    @pytest.mark.asyncio
    async def test_valid_token_allows_through(self):
        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[]),
        ):
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/weekly-pulse", token=CRON_TOKEN)
        assert status == 200

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        with patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/weekly-pulse", token="wrong")
        assert status == 401

    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self):
        with patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/weekly-pulse", token=None)
        assert status == 401


# ---------------------------------------------------------------------------
# Tests: industry-pulse
# ---------------------------------------------------------------------------

class TestIndustryPulseCronAuth:
    @pytest.mark.asyncio
    async def test_valid_token_allows_through(self):
        with (
            patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_industries.list_registered_industries", new_callable=AsyncMock, return_value=[]),
            patch("hephae_api.routers.batch.industry_pulse_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/industry-pulse", token=CRON_TOKEN)
        assert status == 200

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        with patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/industry-pulse", token="bad")
        assert status == 401

    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self):
        with patch("hephae_api.routers.batch.industry_pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/industry-pulse", token=None)
        assert status == 401


# ---------------------------------------------------------------------------
# Tests: reference-harvest
# ---------------------------------------------------------------------------

class TestReferenceHarvestCronAuth:
    @pytest.mark.asyncio
    async def test_valid_token_allows_through(self):
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value={"harvested": 0, "saved": 0, "by_topic": {}}),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/reference-harvest", token=CRON_TOKEN)
        assert status == 200

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        with patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/reference-harvest", token="bad-token")
        assert status == 401

    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self):
        with patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN
            status = await _call_cron("/api/cron/reference-harvest", token=None)
        assert status == 401

    @pytest.mark.asyncio
    async def test_empty_secret_allows_all(self):
        """When CRON_SECRET is empty, all requests pass."""
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value={"harvested": 0, "saved": 0, "by_topic": {}}),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""
            status = await _call_cron("/api/cron/reference-harvest", token=None)
        assert status == 200
