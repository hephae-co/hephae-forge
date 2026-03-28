"""Unit tests for /api/v1/* endpoints.

Covers: valid API key → 200, invalid → 401, missing → 401,
and each of the 5 v1 endpoints with mocked runners.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

BASE_IDENTITY = {
    "name": "Joe's Pizza",
    "address": "123 Main St, Newark, NJ 07102",
    "officialUrl": "https://joespizza.com",
    "competitors": [{"name": "Rival Pizza", "url": "https://rivalpizza.com"}],
}

SAMPLE_ENRICHED_PROFILE = {
    **BASE_IDENTITY,
    "menuUrl": None,
    "phone": "+1 (973) 555-0100",
}

SAMPLE_SEO = {
    "overallScore": 72,
    "url": "https://joespizza.com",
    "sections": [],
}

SAMPLE_COMPETITIVE = {
    "overall_score": 65,
    "market_summary": "Competitive market",
}

SAMPLE_TRAFFIC = {
    "summary": "Peak Fri-Sat evenings",
    "overall_score": 78,
}

SAMPLE_SURGICAL = {
    "overall_score": 80,
    "menu_items": [],
    "strategic_advice": [],
    "identity": BASE_IDENTITY,
    "generated_at": "2026-03-27T00:00:00Z",
}

TEST_API_KEY = "test-v1-api-key"


# ---------------------------------------------------------------------------
# Helper: client with API key patched in
# ---------------------------------------------------------------------------

def _make_client_context(api_key: str | None = TEST_API_KEY):
    """Context manager that patches FORGE_V1_API_KEY and returns AsyncClient."""
    import contextlib

    @contextlib.asynccontextmanager
    async def _ctx():
        with patch.dict(os.environ, {"FORGE_V1_API_KEY": TEST_API_KEY}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac

            importlib.reload(hephae_common.auth)

    return _ctx()


# ---------------------------------------------------------------------------
# Tests: API key auth
# ---------------------------------------------------------------------------

class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self):
        async with _make_client_context() as ac:
            res = await ac.post("/api/v1/seo", json={"identity": BASE_IDENTITY})
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self):
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/seo",
                json={"identity": BASE_IDENTITY},
                headers={"X-Api-Key": "wrong-key"},
            )
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_api_key_passes_auth(self):
        with patch("hephae_agents.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value=SAMPLE_SEO):
            # Just test that a valid key doesn't 401; response may 400 due to missing URL
            async with _make_client_context() as ac:
                # POST with minimal valid body
                res = await ac.post(
                    "/api/v1/seo",
                    json={"identity": BASE_IDENTITY},
                    headers={"X-Api-Key": TEST_API_KEY},
                )
            # Should not be 401 — may be 200 or 500 depending on runner mock
            assert res.status_code != 401

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_through(self):
        """When FORGE_V1_API_KEY is not set, all requests pass (dev mode)."""
        with (
            patch.dict(os.environ, {"FORGE_V1_API_KEY": ""}),
        ):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            try:
                with patch("hephae_agents.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value=SAMPLE_SEO):
                    from hephae_api.main import app
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as ac:
                        res = await ac.post("/api/v1/seo", json={"identity": BASE_IDENTITY})
                # Dev mode: no key configured, should not 401
                assert res.status_code != 401
            finally:
                importlib.reload(hephae_common.auth)


# ---------------------------------------------------------------------------
# Tests: v1/seo
# ---------------------------------------------------------------------------

class TestV1Seo:
    @pytest.mark.asyncio
    async def test_400_when_no_url(self):
        """Missing officialUrl → 400."""
        no_url = {**BASE_IDENTITY, "officialUrl": None}
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/seo",
                json={"identity": no_url},
                headers={"X-Api-Key": TEST_API_KEY},
            )
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_200_with_seo_data(self):
        with (
            patch("hephae_api.routers.v1.seo.InMemorySessionService"),
            patch("hephae_api.routers.v1.seo.Runner") as mock_runner_cls,
            patch("hephae_agents.social.marketing_swarm.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            # Mock the ADK runner to produce a final text response with JSON
            import json

            mock_runner = MagicMock()

            async def _fake_run(**kwargs):
                mock_event = MagicMock()
                mock_part = MagicMock()
                mock_part.text = json.dumps(SAMPLE_SEO)
                mock_part.thought = False
                mock_part.function_call = None
                mock_part.function_response = None
                mock_event.content = MagicMock(parts=[mock_part])
                mock_event.actions = None
                yield mock_event

            mock_runner.run_async = _fake_run
            mock_runner_cls.return_value = mock_runner

            mock_session_service = MagicMock()
            mock_session_service.create_session = AsyncMock()
            mock_session_service.get_session = AsyncMock(return_value=MagicMock(state={}))
            patch("hephae_api.routers.v1.seo.InMemorySessionService", return_value=mock_session_service).start()

            async with _make_client_context() as ac:
                res = await ac.post(
                    "/api/v1/seo",
                    json={"identity": BASE_IDENTITY},
                    headers={"X-Api-Key": TEST_API_KEY},
                )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Tests: v1/discover
# ---------------------------------------------------------------------------

class TestV1Discover:
    @pytest.mark.asyncio
    async def test_400_when_no_query(self):
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/discover",
                json={},
                headers={"X-Api-Key": TEST_API_KEY},
            )
        assert res.status_code == 400
        assert "query" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_404_when_business_not_found(self):
        with patch("hephae_api.routers.v1.discover.LocatorAgent") as mock_locator:
            mock_locator.resolve = AsyncMock(side_effect=RuntimeError("Not found"))

            async with _make_client_context() as ac:
                res = await ac.post(
                    "/api/v1/discover",
                    json={"query": "nonexistent business 99999"},
                    headers={"X-Api-Key": TEST_API_KEY},
                )
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Tests: v1/competitive
# ---------------------------------------------------------------------------

class TestV1Competitive:
    @pytest.mark.asyncio
    async def test_400_when_no_competitors(self):
        no_comp = {**BASE_IDENTITY, "competitors": []}
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/competitive",
                json={"identity": no_comp},
                headers={"X-Api-Key": TEST_API_KEY},
            )
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_200_with_competitive_data(self):
        with (
            patch("hephae_api.routers.v1.competitive.run_competitive_analysis", new_callable=AsyncMock, return_value=SAMPLE_COMPETITIVE),
            patch("hephae_agents.social.marketing_swarm.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            async with _make_client_context() as ac:
                res = await ac.post(
                    "/api/v1/competitive",
                    json={"identity": BASE_IDENTITY},
                    headers={"X-Api-Key": TEST_API_KEY},
                )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["market_summary"] == "Competitive market"


# ---------------------------------------------------------------------------
# Tests: v1/traffic
# ---------------------------------------------------------------------------

class TestV1Traffic:
    @pytest.mark.asyncio
    async def test_400_when_no_name(self):
        no_name = {**BASE_IDENTITY, "name": None}
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/traffic",
                json={"identity": no_name},
                headers={"X-Api-Key": TEST_API_KEY},
            )
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_200_with_traffic_data(self):
        with (
            patch("hephae_api.routers.v1.traffic.ForecasterAgent") as mock_fa,
            patch("hephae_agents.social.marketing_swarm.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            mock_fa.forecast = AsyncMock(return_value=SAMPLE_TRAFFIC)

            async with _make_client_context() as ac:
                res = await ac.post(
                    "/api/v1/traffic",
                    json={"identity": BASE_IDENTITY},
                    headers={"X-Api-Key": TEST_API_KEY},
                )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["summary"] == "Peak Fri-Sat evenings"


# ---------------------------------------------------------------------------
# Tests: v1/analyze
# ---------------------------------------------------------------------------

class TestV1Analyze:
    @pytest.mark.asyncio
    async def test_400_when_no_menu_screenshot(self):
        async with _make_client_context() as ac:
            res = await ac.post(
                "/api/v1/analyze",
                json={"identity": BASE_IDENTITY},
                headers={"X-Api-Key": TEST_API_KEY},
            )
        assert res.status_code == 400
        assert "menu" in res.json()["error"].lower()
