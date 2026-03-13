"""
Unit tests for POST /api/capabilities/competitive

Covers: input validation (competitors required), runner delegation,
report upload, error handling.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IDENTITY_WITH_COMPETITORS = {
    "name": "Bosphorus Restaurant",
    "address": "10 Main St, Nutley, NJ 07110",
    "officialUrl": "https://bosphorusnutley.com",
    "competitors": [
        {"name": "Turkish Kitchen", "url": "https://turkishkitchen.com", "reason": "Same cuisine"},
        {"name": "Istanbul Grill", "url": "https://istanbulgrill.com", "reason": "Same neighborhood"},
    ],
}

COMPETITIVE_PAYLOAD = {
    "market_summary": "Bosphorus is positioned mid-market.",
    "competitor_profiles": [
        {"name": "Turkish Kitchen", "strengths": ["Good reviews"], "weaknesses": ["Limited menu"]},
    ],
    "positioning": {"price_tier": "mid-range", "differentiation": "Authentic Turkish cuisine"},
    "recommendations": ["Expand delivery radius", "Add catering option"],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    with (
        patch("backend.routers.web.capabilities.run_competitive_analysis", new_callable=AsyncMock, return_value=COMPETITIVE_PAYLOAD),
        patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/competitive.html"),
        patch("backend.routers.web.capabilities.build_competitive_report", return_value="<html>comp</html>"),
        patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
    ):
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    @pytest.mark.asyncio
    async def test_400_no_competitors(self, client):
        res = await client.post("/api/capabilities/competitive", json={"identity": {"name": "Test", "officialUrl": "https://test.com"}})
        assert res.status_code == 400
        assert "competitors" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_400_empty_competitors(self, client):
        identity = {**IDENTITY_WITH_COMPETITORS, "competitors": []}
        res = await client.post("/api/capabilities/competitive", json={"identity": identity})
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Successful pipeline
# ---------------------------------------------------------------------------

class TestSuccessfulPipeline:
    @pytest.mark.asyncio
    async def test_returns_competitive_report(self, client):
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        data = res.json()
        assert data["market_summary"] == "Bosphorus is positioned mid-market."
        assert "reportUrl" in data

    @pytest.mark.asyncio
    async def test_report_url_attached(self, client):
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        assert res.json()["reportUrl"] == "https://storage.googleapis.com/test/competitive.html"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_500_on_runner_error(self):
        with (
            patch("backend.routers.web.capabilities.run_competitive_analysis", new_callable=AsyncMock, side_effect=ValueError("Runner failed")),
            patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value=None),
            patch("backend.routers.web.capabilities.build_competitive_report", return_value=""),
            patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower()),
            patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
            patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
                assert res.status_code == 500
                assert "Runner failed" in res.json()["error"]
