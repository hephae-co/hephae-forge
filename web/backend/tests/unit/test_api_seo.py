"""
Unit tests for POST /api/capabilities/seo

Covers: missing officialUrl -> 400, successful report passthrough (200),
robust JSON extraction (prose, fences, trailing commas), isAnalyzed injection,
empty-output fallback, thought parts filtering.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_part(text=None, thought=False, function_call=None, function_response=None):
    """Create an ADK-style part object."""
    p = SimpleNamespace()
    if text is not None:
        p.text = text
    p.thought = thought
    p.function_call = function_call
    p.function_response = function_response
    return p


def _make_event(*parts):
    """Create an ADK-style event with content.parts."""
    return SimpleNamespace(content=SimpleNamespace(parts=list(parts)))


def _make_stream(*events):
    """Return a factory for an async generator yielding the given events."""
    async def _gen(*a, **kw):
        for ev in events:
            yield ev
    return _gen


def _empty_stream(*a, **kw):
    async def _gen():
        return
        yield
    return _gen()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    mock_session_svc = MagicMock()
    mock_session_svc.create_session = AsyncMock(return_value=None)
    mock_session_svc.get_session = AsyncMock(return_value=MagicMock(state={}))

    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(side_effect=_empty_stream)

    with (
        patch("backend.routers.capabilities.seo.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.capabilities.seo.Runner", return_value=mock_runner),
        patch("backend.routers.capabilities.seo.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/report.html"),
        patch("backend.routers.capabilities.seo.build_seo_report", return_value="<html>report</html>"),
        patch("backend.routers.capabilities.seo.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.capabilities.seo.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.capabilities.seo.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
    ):
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._runner = mock_runner  # type: ignore[attr-defined]
            yield ac


def _set_stream(client, *events):
    """Configure the mock runner to yield given events."""
    client._runner.run_async = MagicMock(side_effect=_make_stream(*events))


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
    async def test_parses_json_output(self, client):
        report = {"overallScore": 88, "summary": "Strong.", "sections": [
            {"id": "technical", "title": "Technical SEO", "score": 90, "recommendations": [
                {"severity": "Info", "title": "Good", "description": "OK", "action": "None"}
            ]}
        ]}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        assert res.status_code == 200
        data = res.json()
        assert data["overallScore"] == 88
        assert len(data["sections"]) == 1
        assert data["sections"][0]["isAnalyzed"] is True

    @pytest.mark.asyncio
    async def test_attaches_target_url(self, client):
        report = {"overallScore": 55, "summary": "OK", "sections": []}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://mybiz.io"}})
        data = res.json()
        assert data["url"] == "https://mybiz.io"

    @pytest.mark.asyncio
    async def test_empty_report_on_no_output(self, client):
        # Empty stream
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Test", "officialUrl": "https://testbiz.com"}})
        assert res.status_code == 200
        data = res.json()
        assert data["url"] == "https://testbiz.com"
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 0

    @pytest.mark.asyncio
    async def test_empty_report_on_non_json_output(self, client):
        _set_stream(client, _make_event(_make_part("Analysis complete. Score is great!")))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        assert res.status_code == 200
        data = res.json()
        assert data["url"] == "https://biz.com"
        assert len(data["sections"]) == 0

    @pytest.mark.asyncio
    async def test_normalises_missing_sections(self, client):
        report = {"overallScore": 45, "summary": "Minimal."}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Test", "officialUrl": "https://test.com"}})
        data = res.json()
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 0


# ---------------------------------------------------------------------------
# JSON extraction robustness
# ---------------------------------------------------------------------------

class TestJsonExtraction:
    @pytest.mark.asyncio
    async def test_strips_json_fences(self, client):
        report = {"overallScore": 77, "summary": "Fenced", "sections": []}
        _set_stream(client, _make_event(_make_part(f"```json\n{json.dumps(report)}\n```")))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        assert res.json()["overallScore"] == 77

    @pytest.mark.asyncio
    async def test_extracts_from_prose(self, client):
        report = {"overallScore": 82, "summary": "Found via extraction.", "sections": []}
        text = f"Here is the SEO report:\n\n{json.dumps(report)}\n\nI hope this helps!"
        _set_stream(client, _make_event(_make_part(text)))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        data = res.json()
        assert data["overallScore"] == 82
        assert data["summary"] == "Found via extraction."

    @pytest.mark.asyncio
    async def test_recovers_trailing_commas(self, client):
        bad_json = '{"overallScore": 65, "summary": "Fixed trailing", "sections": [{"id": "tech", "title": "Technical", "score": 70, "recommendations": [],},],}'
        _set_stream(client, _make_event(_make_part(bad_json)))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Biz", "officialUrl": "https://biz.com"}})
        assert res.json()["overallScore"] == 65


# ---------------------------------------------------------------------------
# Section normalization
# ---------------------------------------------------------------------------

class TestSectionNormalization:
    @pytest.mark.asyncio
    async def test_is_analyzed_and_recommendations_array(self, client):
        report = {"overallScore": 75, "summary": "Test.", "sections": [
            {"id": "technical", "title": "Technical SEO", "score": 80, "recommendations": [
                {"severity": "Warning", "title": "T1", "description": "D1", "action": "A1"}
            ]},
            {"id": "content", "title": "Content Quality", "score": 60},
        ]}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Test", "officialUrl": "https://test.com"}})
        data = res.json()
        assert data["sections"][0]["isAnalyzed"] is True
        assert data["sections"][1]["isAnalyzed"] is True
        assert isinstance(data["sections"][1]["recommendations"], list)
        assert len(data["sections"][1]["recommendations"]) == 0


# ---------------------------------------------------------------------------
# Multi-part and thinking
# ---------------------------------------------------------------------------

class TestMultiPartAndThinking:
    @pytest.mark.asyncio
    async def test_accumulates_multi_part(self, client):
        report = {"overallScore": 91, "summary": "Multi-part.", "sections": []}
        full = json.dumps(report)
        half = len(full) // 2
        _set_stream(
            client,
            _make_event(_make_part(full[:half])),
            _make_event(_make_part(full[half:])),
        )
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Multi", "officialUrl": "https://multi.com"}})
        assert res.json()["overallScore"] == 91

    @pytest.mark.asyncio
    async def test_filters_thinking_parts(self, client):
        report = {"overallScore": 70, "summary": "After thinking.", "sections": []}
        _set_stream(
            client,
            _make_event(_make_part("Let me analyze...", thought=True)),
            _make_event(_make_part(function_call={"name": "googleSearch", "args": {"query": "site:test.com"}})),
            _make_event(_make_part(function_response={"name": "googleSearch", "response": {}})),
            _make_event(_make_part("Compiling report...", thought=True)),
            _make_event(_make_part(json.dumps(report))),
        )
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Think", "officialUrl": "https://think.com"}})
        data = res.json()
        assert data["overallScore"] == 70
        assert data["summary"] == "After thinking."

    @pytest.mark.asyncio
    async def test_thought_fallback(self, client):
        report = {"overallScore": 82, "summary": "Recovered from thought.", "sections": [
            {"id": "technical", "title": "Technical SEO", "score": 85, "recommendations": []}
        ]}
        _set_stream(
            client,
            _make_event(_make_part("Let me run the audit...", thought=True)),
            _make_event(_make_part(json.dumps(report), thought=True)),
        )
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Thought", "officialUrl": "https://thought.com"}})
        assert res.status_code == 200
        data = res.json()
        assert data["overallScore"] == 82
        assert data["sections"][0]["isAnalyzed"] is True


# ---------------------------------------------------------------------------
# Full audit with 5 sections
# ---------------------------------------------------------------------------

class TestFullAudit:
    @pytest.mark.asyncio
    async def test_5_sections(self, client):
        sections = [
            {"id": "technical", "title": "Technical SEO", "score": 80, "recommendations": [{"severity": "Warning", "title": "T1", "description": "D", "action": "A"}]},
            {"id": "content", "title": "Content Quality", "score": 65, "recommendations": []},
            {"id": "ux", "title": "User Experience", "score": 72, "recommendations": []},
            {"id": "performance", "title": "Performance", "score": 55, "recommendations": []},
            {"id": "authority", "title": "Backlinks & Authority", "score": 40, "recommendations": []},
        ]
        report = {"overallScore": 62, "summary": "Full audit.", "sections": sections}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Full", "officialUrl": "https://full.com"}})
        data = res.json()
        assert len(data["sections"]) == 5
        ids = [s["id"] for s in data["sections"]]
        assert ids == ["technical", "content", "ux", "performance", "authority"]

    @pytest.mark.asyncio
    async def test_partial_audit(self, client):
        report = {"overallScore": 45, "summary": "Partial.", "sections": [
            {"id": "technical", "title": "Technical SEO", "score": 60, "recommendations": []},
            {"id": "content", "title": "Content Quality", "score": 30, "recommendations": []},
        ]}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Partial", "officialUrl": "https://partial.com"}})
        data = res.json()
        assert len(data["sections"]) < 5
        assert len(data["sections"]) == 2

    @pytest.mark.asyncio
    async def test_zero_scores(self, client):
        report = {"overallScore": 10, "summary": "All zeros.", "sections": [
            {"id": "technical", "title": "Technical SEO", "score": 0, "recommendations": []},
            {"id": "performance", "title": "Performance", "score": 0, "recommendations": []},
        ]}
        _set_stream(client, _make_event(_make_part(json.dumps(report))))
        res = await client.post("/api/capabilities/seo", json={"identity": {"name": "Zero", "officialUrl": "https://zero.com"}})
        data = res.json()
        assert len(data["sections"]) == 2
        assert data["sections"][0]["score"] == 0
        assert data["sections"][0]["isAnalyzed"] is True
