"""Unit tests for POST /api/overview.

Covers: valid POST returns business overview shape, HMAC auth required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


BASE_IDENTITY = {
    "name": "Joe's Diner",
    "address": "123 Main St, Nutley, NJ 07110",
    "officialUrl": "https://joesdiner.com",
}

SAMPLE_OVERVIEW = {
    "name": "Joe's Diner",
    "summary": "A classic American diner serving breakfast all day.",
    "hours": "Mon-Sun 7am-10pm",
    "phone": "+1 (973) 555-1234",
    "address": "123 Main St, Nutley, NJ 07110",
    "googleMapsUrl": "https://maps.google.com/?q=joes+diner",
}


@pytest_asyncio.fixture
async def client():
    with (
        patch("hephae_api.routers.web.overview.verify_request", return_value=None),
        patch("hephae_agents.business_overview.runner.run_business_overview", new_callable=AsyncMock, return_value=SAMPLE_OVERVIEW),
    ):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestOverviewEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_overview_data(self, client):
        res = await client.post("/api/overview", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Joe's Diner"
        assert data["summary"] == "A classic American diner serving breakfast all day."

    @pytest.mark.asyncio
    async def test_400_when_identity_missing(self, client):
        res = await client.post("/api/overview", json={})
        assert res.status_code == 400
        assert "identity" in res.json()["error"].lower() or "missing" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_400_when_name_missing(self, client):
        res = await client.post("/api/overview", json={"identity": {"address": "123 Main St"}})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_hmac_auth_required(self):
        """When FORGE_API_SECRET is set, missing HMAC headers → 401."""
        import os
        import importlib
        import hephae_common.auth

        old_secret = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = "test-secret"
        importlib.reload(hephae_common.auth)

        try:
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/overview", json={"identity": BASE_IDENTITY})
            assert res.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old_secret
            importlib.reload(hephae_common.auth)

    @pytest.mark.asyncio
    async def test_returns_all_overview_fields(self, client):
        res = await client.post("/api/overview", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["hours"] == "Mon-Sun 7am-10pm"
        assert data["phone"] == "+1 (973) 555-1234"
        assert "googleMapsUrl" in data
