"""Unit tests for /api/capabilities/* endpoints.

Covers: seo, competitive, traffic, marketing — 200 shape, 400 validation,
401 auth (via verify_request HMAC dependency).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Shared sample payloads
# ---------------------------------------------------------------------------

BASE_IDENTITY = {
    "name": "Bosphorus Restaurant",
    "address": "10 Main St, Nutley, NJ 07110",
    "officialUrl": "https://bosphorusnutley.com",
    "competitors": [{"name": "Rival", "url": "https://rival.com"}],
}

SAMPLE_SEO = {
    "overallScore": 72,
    "summary": "Decent SEO, missing meta tags",
    "url": "https://bosphorusnutley.com",
    "sections": [],
}

SAMPLE_COMPETITIVE = {
    "overall_score": 65,
    "market_summary": "Strong local competition",
    "competitors": [],
}

SAMPLE_TRAFFIC = {
    "summary": "Peak hours: Fri/Sat 7-9pm",
    "overall_score": 80,
    "forecast": {},
}

SAMPLE_MARKETING = {
    "summary": "Social media audit complete",
    "overallScore": 70,
    "platforms": [],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_ctx(identity: dict | None = None):
    ctx = MagicMock()
    ctx.identity = identity or BASE_IDENTITY
    return ctx


@pytest_asyncio.fixture
async def client():
    """TestClient with all capability runners mocked out."""
    mock_ctx = _make_mock_ctx()

    with (
        patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
        patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=mock_ctx),
        patch("hephae_api.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, return_value=SAMPLE_SEO),
        patch("hephae_api.routers.web.capabilities.run_competitive_analysis", new_callable=AsyncMock, return_value=SAMPLE_COMPETITIVE),
        patch("hephae_api.routers.web.capabilities.ForecasterAgent") as mock_forecaster,
        patch("hephae_api.routers.web.capabilities.run_social_media_audit", new_callable=AsyncMock, return_value=SAMPLE_MARKETING),
        patch("hephae_api.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://cdn.test/report.html"),
        patch("hephae_api.routers.web.capabilities.build_seo_report", return_value="<html>seo</html>"),
        patch("hephae_api.routers.web.capabilities.build_competitive_report", return_value="<html>comp</html>"),
        patch("hephae_api.routers.web.capabilities.build_traffic_report", return_value="<html>traffic</html>"),
        patch("hephae_api.routers.web.capabilities.build_social_audit_report", return_value="<html>social</html>"),
        patch("hephae_api.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
        patch("hephae_api.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        patch("hephae_api.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
    ):
        mock_forecaster.forecast = AsyncMock(return_value=SAMPLE_TRAFFIC)

        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def authed_client():
    """TestClient with optional_firebase_user injected."""
    mock_ctx = _make_mock_ctx()
    mock_user = {"uid": "user-1", "email": "test@example.com"}

    with (
        patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
        patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=mock_ctx),
        patch("hephae_api.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, return_value=SAMPLE_SEO),
        patch("hephae_api.routers.web.capabilities.run_competitive_analysis", new_callable=AsyncMock, return_value=SAMPLE_COMPETITIVE),
        patch("hephae_api.routers.web.capabilities.ForecasterAgent") as mock_forecaster,
        patch("hephae_api.routers.web.capabilities.run_social_media_audit", new_callable=AsyncMock, return_value=SAMPLE_MARKETING),
        patch("hephae_api.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://cdn.test/report.html"),
        patch("hephae_api.routers.web.capabilities.build_seo_report", return_value="<html/>"),
        patch("hephae_api.routers.web.capabilities.build_competitive_report", return_value="<html/>"),
        patch("hephae_api.routers.web.capabilities.build_traffic_report", return_value="<html/>"),
        patch("hephae_api.routers.web.capabilities.build_social_audit_report", return_value="<html/>"),
        patch("hephae_api.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
        patch("hephae_api.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        patch("hephae_api.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
    ):
        mock_forecaster.forecast = AsyncMock(return_value=SAMPLE_TRAFFIC)

        from hephae_api.main import app
        from hephae_api.lib.auth import optional_firebase_user

        app.dependency_overrides[optional_firebase_user] = lambda: mock_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        app.dependency_overrides.pop(optional_firebase_user, None)


# ---------------------------------------------------------------------------
# SEO endpoint
# ---------------------------------------------------------------------------

class TestSeoEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_seo_report(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["overallScore"] == 72
        assert data["summary"] == "Decent SEO, missing meta tags"

    @pytest.mark.asyncio
    async def test_includes_report_url(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        assert res.json()["reportUrl"] == "https://cdn.test/report.html"

    @pytest.mark.asyncio
    async def test_seo_400_when_no_url(self):
        """SEO requires officialUrl."""
        no_url_ctx = _make_mock_ctx({**BASE_IDENTITY, "officialUrl": None})
        with (
            patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
            patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=no_url_ctx),
        ):
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/seo", json={"identity": {**BASE_IDENTITY, "officialUrl": None}})
        assert res.status_code == 400
        assert "url" in res.json()["error"].lower() or "seo" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_seo_401_when_auth_missing(self):
        """HMAC auth required; when FORGE_API_SECRET is set, missing headers → 401."""
        import os
        old_secret = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = "test-secret"
        try:
            # Re-import to pick up env change
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/seo", json={"identity": BASE_IDENTITY})
            assert res.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old_secret
            importlib.reload(hephae_common.auth)


# ---------------------------------------------------------------------------
# Competitive endpoint
# ---------------------------------------------------------------------------

class TestCompetitiveEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_competitive_report(self, client):
        res = await client.post("/api/capabilities/competitive", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["market_summary"] == "Strong local competition"

    @pytest.mark.asyncio
    async def test_competitive_400_when_no_competitors(self):
        """Missing competitors array → 400."""
        no_comp_ctx = _make_mock_ctx({**BASE_IDENTITY, "competitors": []})
        with (
            patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
            patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=no_comp_ctx),
        ):
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/competitive", json={"identity": {**BASE_IDENTITY, "competitors": []}})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_competitive_includes_report_url(self, client):
        res = await client.post("/api/capabilities/competitive", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        assert "reportUrl" in res.json()


# ---------------------------------------------------------------------------
# Traffic endpoint
# ---------------------------------------------------------------------------

class TestTrafficEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_traffic_forecast(self, client):
        res = await client.post("/api/capabilities/traffic", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["summary"] == "Peak hours: Fri/Sat 7-9pm"

    @pytest.mark.asyncio
    async def test_traffic_400_when_no_name(self):
        """Missing name → 400."""
        no_name_ctx = _make_mock_ctx({**BASE_IDENTITY, "name": None})
        with (
            patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
            patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=no_name_ctx),
        ):
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/traffic", json={"identity": {**BASE_IDENTITY, "name": None}})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_traffic_includes_report_url(self, client):
        res = await client.post("/api/capabilities/traffic", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        assert "reportUrl" in res.json()


# ---------------------------------------------------------------------------
# Marketing endpoint
# ---------------------------------------------------------------------------

class TestMarketingEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200_with_marketing_report(self, client):
        res = await client.post("/api/capabilities/marketing", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["summary"] == "Social media audit complete"

    @pytest.mark.asyncio
    async def test_marketing_400_when_no_name(self):
        """Missing name → 400."""
        no_name_ctx = _make_mock_ctx({**BASE_IDENTITY, "name": None})
        with (
            patch("hephae_api.routers.web.capabilities.verify_request", return_value=None),
            patch("hephae_api.routers.web.capabilities.build_business_context", new_callable=AsyncMock, return_value=no_name_ctx),
        ):
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/marketing", json={"identity": {**BASE_IDENTITY, "name": None}})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_marketing_includes_report_url(self, client):
        res = await client.post("/api/capabilities/marketing", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        assert "reportUrl" in res.json()
