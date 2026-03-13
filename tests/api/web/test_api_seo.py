"""
Unit tests for POST /api/capabilities/seo

Covers: missing officialUrl -> 400, successful report passthrough (200),
section normalization, report URL attachment, error handling.

Note: JSON extraction and streaming tests are in the SEO runner unit tests.
The endpoint delegates all ADK logic to run_seo_audit().
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEO_REPORT = {
    "overallScore": 88,
    "summary": "Strong.",
    "url": "https://biz.com",
    "sections": [
        {"id": "technical", "title": "Technical SEO", "score": 90, "isAnalyzed": True, "recommendations": [
            {"severity": "Info", "title": "Good", "description": "OK", "action": "None"}
        ]},
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    with (
        patch("backend.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, return_value=SEO_REPORT),
        patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/report.html"),
        patch("backend.routers.web.capabilities.build_seo_report", return_value="<html>report</html>"),
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
    async def test_400_no_url(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Test Business"}})
        assert res.status_code == 400
        assert "url" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_400_empty_url(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Test", "officialUrl": ""}})
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Successful runs
# ---------------------------------------------------------------------------

class TestSuccessfulRun:
    @pytest.mark.asyncio
    async def test_returns_seo_report(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        assert res.status_code == 200
        data = res.json()
        assert data["overallScore"] == 88
        assert len(data["sections"]) == 1
        assert data["sections"][0]["isAnalyzed"] is True

    @pytest.mark.asyncio
    async def test_attaches_target_url(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        data = res.json()
        assert data["url"] == "https://biz.com"

    @pytest.mark.asyncio
    async def test_attaches_report_url(self, client):
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        data = res.json()
        assert data["reportUrl"] == "https://storage.googleapis.com/test/report.html"

    @pytest.mark.asyncio
    async def test_empty_report(self):
        empty_report = {"overallScore": 0, "summary": "", "url": "https://test.com", "sections": []}
        with (
            patch("backend.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, return_value=empty_report),
            patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value=None),
            patch("backend.routers.web.capabilities.build_seo_report", return_value=""),
            patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower()),
            patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
            patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/seo", json={"identity": {"name": "Test", "officialUrl": "https://test.com"}})
                assert res.status_code == 200
                data = res.json()
                assert isinstance(data["sections"], list)
                assert len(data["sections"]) == 0


# ---------------------------------------------------------------------------
# Section normalization (verified through runner output)
# ---------------------------------------------------------------------------

class TestSectionNormalization:
    @pytest.mark.asyncio
    async def test_full_5_sections(self):
        sections = [
            {"id": "technical", "title": "Technical SEO", "score": 80, "isAnalyzed": True, "recommendations": []},
            {"id": "content", "title": "Content Quality", "score": 65, "isAnalyzed": True, "recommendations": []},
            {"id": "ux", "title": "User Experience", "score": 72, "isAnalyzed": True, "recommendations": []},
            {"id": "performance", "title": "Performance", "score": 55, "isAnalyzed": True, "recommendations": []},
            {"id": "authority", "title": "Backlinks & Authority", "score": 40, "isAnalyzed": True, "recommendations": []},
        ]
        report = {"overallScore": 62, "summary": "Full audit.", "url": "https://full.com", "sections": sections}
        with (
            patch("backend.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, return_value=report),
            patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value=None),
            patch("backend.routers.web.capabilities.build_seo_report", return_value=""),
            patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower()),
            patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
            patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/seo", json={"identity": {"name": "Full", "officialUrl": "https://full.com"}})
                data = res.json()
                assert len(data["sections"]) == 5
                ids = [s["id"] for s in data["sections"]]
                assert ids == ["technical", "content", "ux", "performance", "authority"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_500_on_runner_error(self):
        with (
            patch("backend.routers.web.capabilities.run_seo_audit", new_callable=AsyncMock, side_effect=ValueError("No URL available")),
            patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock),
            patch("backend.routers.web.capabilities.build_seo_report", return_value=""),
            patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower()),
            patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
            patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/seo", json={"identity": {"name": "Err", "officialUrl": "https://err.com"}})
                assert res.status_code == 500
