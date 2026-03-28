"""Unit tests for GET /api/cron/reference-harvest.

Covers: auth (valid/invalid/missing), mock harvester, response shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


CRON_TOKEN = "ref-harvest-secret"

SAMPLE_HARVEST_RESULT = {
    "harvested": 12,
    "saved": 8,
    "by_topic": {
        "restaurant_margins": 4,
        "food_costs": 3,
        "labor": 1,
    },
}


class TestReferenceHarvestCronAuth:
    @pytest.mark.asyncio
    async def test_valid_bearer_token_returns_200(self):
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value=SAMPLE_HARVEST_RESULT),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = CRON_TOKEN

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/reference-harvest",
                    headers={"Authorization": f"Bearer {CRON_TOKEN}"},
                )

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        with patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/reference-harvest",
                    headers={"Authorization": "Bearer wrong-token"},
                )

        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_returns_401(self):
        with patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = CRON_TOKEN

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/reference-harvest")

        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_cron_secret_allows_through(self):
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value=SAMPLE_HARVEST_RESULT),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/reference-harvest")

        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_x_cron_secret_header_accepted(self):
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value=SAMPLE_HARVEST_RESULT),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = CRON_TOKEN

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/reference-harvest",
                    headers={"X-Cron-Secret": f"Bearer {CRON_TOKEN}"},
                )

        assert res.status_code == 200


class TestReferenceHarvestCronBehavior:
    @pytest.mark.asyncio
    async def test_returns_harvest_stats(self):
        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", new_callable=AsyncMock, return_value=SAMPLE_HARVEST_RESULT),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/reference-harvest")

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["harvested"] == 12
        assert data["saved"] == 8
        assert "by_topic" in data

    @pytest.mark.asyncio
    async def test_calls_run_weekly_harvest(self):
        mock_harvest = AsyncMock(return_value=SAMPLE_HARVEST_RESULT)

        with (
            patch("hephae_api.routers.batch.reference_cron.settings") as mock_settings,
            patch("hephae_agents.research.reference_harvester.run_weekly_harvest", mock_harvest),
            patch("hephae_api.routers.batch.reference_cron._send_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                await ac.get("/api/cron/reference-harvest")

        mock_harvest.assert_called_once()
