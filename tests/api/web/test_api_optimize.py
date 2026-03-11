"""Unit tests for POST /api/optimize endpoints."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="optimize router removed")

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """Fresh client with optimizer mocked."""
    with (
        patch("backend.routers.web.optimize.run_optimizer", new_callable=AsyncMock, return_value={"status": "ok", "run_at": "2026-03-03T00:00:00Z", "duration_seconds": 1.0}),
        patch("backend.routers.web.optimize._run_prompt_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
        patch("backend.routers.web.optimize._run_ai_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
        patch("backend.routers.web.optimize._run_cloud_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
        patch("backend.routers.web.optimize._run_performance_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
    ):
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestOptimizeEndpoint:
    @pytest.mark.asyncio
    async def test_post_optimize_returns_200(self, client):
        res = await client.post("/api/optimize", json={"optimizers": ["all"]})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_post_optimize_default_body(self, client):
        res = await client.post("/api/optimize", json={})
        assert res.status_code == 200


class TestIndividualEndpoints:
    @pytest.mark.asyncio
    async def test_prompt_endpoint(self, client):
        res = await client.post("/api/optimize/prompt", json={})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_ai_cost_endpoint(self, client):
        res = await client.post("/api/optimize/ai-cost", json={})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_performance_endpoint(self, client):
        res = await client.post("/api/optimize/performance", json={})
        assert res.status_code == 200
