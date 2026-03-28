"""Unit tests for GET /api/cron/weekly-pulse.

Covers: valid cron secret → 200, invalid → 401, missing → 401,
CRON_SECRET not set → allows through.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_zip(zip_code: str = "07110", business_types: list[str] | None = None) -> dict:
    return {
        "zipCode": zip_code,
        "businessTypes": business_types or ["Restaurants"],
        "city": "Nutley",
        "state": "NJ",
        "status": "active",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWeeklyPulseCronAuth:
    @pytest.mark.asyncio
    async def test_valid_bearer_token_returns_200(self):
        """Valid Bearer token → 200 and triggers pulse."""
        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[]),
        ):
            mock_settings.CRON_SECRET = "super-secret"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/weekly-pulse",
                    headers={"Authorization": "Bearer super-secret"},
                )
        assert res.status_code == 200
        data = res.json()
        assert "triggered" in data
        assert data["triggered"] == 0
        assert data["skipped"] == 0

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self):
        """Wrong token → 401."""
        with patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = "super-secret"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/weekly-pulse",
                    headers={"Authorization": "Bearer wrong-token"},
                )
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        """No auth → 401."""
        with patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings:
            mock_settings.CRON_SECRET = "super-secret"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/weekly-pulse")
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_cron_secret_allows_through(self):
        """When CRON_SECRET is empty/unset, all requests pass through."""
        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[]),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/weekly-pulse")
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_x_cron_secret_header_accepted(self):
        """X-Cron-Secret header is also accepted."""
        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[]),
        ):
            mock_settings.CRON_SECRET = "super-secret"

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/weekly-pulse",
                    headers={"X-Cron-Secret": "Bearer super-secret"},
                )
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_triggers_pulses_for_active_zips(self):
        """Active zips without existing pulse are scheduled."""
        import asyncio as _asyncio

        zip_doc = _mock_zip("07110")

        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[zip_doc]),
            patch("hephae_db.firestore.weekly_pulse.get_latest_pulse", new_callable=AsyncMock, return_value=None),
            patch("hephae_api.routers.batch.pulse_cron._run_single_pulse", new_callable=AsyncMock, return_value={"zipCode": "07110", "businessType": "Restaurants", "status": "completed", "pulseId": "pulse-1"}),
            patch("hephae_api.routers.batch.pulse_cron._send_cron_summary_email", new_callable=AsyncMock),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/weekly-pulse")

        assert res.status_code == 200
        data = res.json()
        assert data["triggered"] == 1
        assert data["skipped"] == 0

    @pytest.mark.asyncio
    async def test_skips_zip_with_existing_pulse_this_week(self):
        """Zip that already has a pulse for current week is skipped."""
        from datetime import datetime

        zip_doc = _mock_zip("07110")
        now = datetime.utcnow()
        week_of = f"{now.year}-W{now.isocalendar()[1]:02d}"

        with (
            patch("hephae_api.routers.batch.pulse_cron.settings") as mock_settings,
            patch("hephae_db.firestore.registered_zipcodes.list_registered_zipcodes", new_callable=AsyncMock, return_value=[zip_doc]),
            patch("hephae_db.firestore.weekly_pulse.get_latest_pulse", new_callable=AsyncMock, return_value={"weekOf": week_of}),
        ):
            mock_settings.CRON_SECRET = ""

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get("/api/cron/weekly-pulse")

        assert res.status_code == 200
        data = res.json()
        assert data["triggered"] == 0
        assert data["skipped"] == 1
