"""
Unit tests for POST /api/capabilities/competitive

Covers: input validation (competitors required), 2-step pipeline
(Profiler -> Positioning), JSON extraction, error handling.
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


def _make_text_event(text: str, thought=False):
    part = SimpleNamespace(text=text, thought=thought, function_call=None, function_response=None)
    return SimpleNamespace(content=SimpleNamespace(parts=[part]))


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

    runners_created = []

    def _make_runner(*a, **kw):
        r = MagicMock()
        r.run_async = MagicMock(side_effect=_empty_stream)
        runners_created.append(r)
        return r

    with (
        patch("backend.routers.web.capabilities.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.web.capabilities.Runner", side_effect=_make_runner),
        patch("backend.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/competitive.html"),
        patch("backend.routers.web.capabilities.build_competitive_report", return_value="<html>comp</html>"),
        patch("backend.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.web.capabilities.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
    ):
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._runners = runners_created  # type: ignore[attr-defined]
            yield ac


def _setup_two_step(client, profiler_text: str, positioning_text: str):
    """Configure the two runners for a Profiler → Positioning pipeline."""
    client._runners.clear()
    call_idx = {"n": 0}

    def _make_runner(*a, **kw):
        r = MagicMock()
        idx = call_idx["n"]
        call_idx["n"] += 1

        if idx == 0:
            async def _profiler(*a2, **kw2):
                yield _make_text_event(profiler_text)
            r.run_async = MagicMock(side_effect=_profiler)
        elif idx == 1:
            async def _positioning(*a2, **kw2):
                yield _make_text_event(positioning_text)
            r.run_async = MagicMock(side_effect=_positioning)
        else:
            r.run_async = MagicMock(side_effect=_empty_stream)

        client._runners.append(r)
        return r

    import backend.routers.web.capabilities as mod
    mod.Runner = MagicMock(side_effect=_make_runner)


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
    async def test_parses_competitive_report(self, client):
        _setup_two_step(
            client,
            profiler_text="Turkish Kitchen is a well-reviewed competitor...",
            positioning_text=json.dumps(COMPETITIVE_PAYLOAD),
        )
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        data = res.json()
        assert data["market_summary"] == "Bosphorus is positioned mid-market."
        assert "reportUrl" in data

    @pytest.mark.asyncio
    async def test_extracts_json_from_fences(self, client):
        _setup_two_step(
            client,
            profiler_text="Competitor brief here.",
            positioning_text=f"```json\n{json.dumps(COMPETITIVE_PAYLOAD)}\n```",
        )
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        assert res.json()["market_summary"] == "Bosphorus is positioned mid-market."

    @pytest.mark.asyncio
    async def test_extracts_json_from_prose(self, client):
        text = f"Here is the report:\n{json.dumps(COMPETITIVE_PAYLOAD)}\nHope this helps!"
        _setup_two_step(client, "Brief.", text)
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        assert res.json()["market_summary"] == "Bosphorus is positioned mid-market."


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_500_on_invalid_json(self, client):
        _setup_two_step(client, "Brief.", "This is not JSON at all")
        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 500

    @pytest.mark.asyncio
    async def test_filters_thinking_parts(self, client):
        """Thinking parts from Gemini 2.5 Pro should be skipped."""
        client._runners.clear()
        call_idx = {"n": 0}

        def _make_runner(*a, **kw):
            r = MagicMock()
            idx = call_idx["n"]
            call_idx["n"] += 1

            if idx == 0:
                async def _profiler(*a2, **kw2):
                    yield _make_text_event("thinking...", thought=True)
                    yield _make_text_event("Turkish Kitchen review.")
                r.run_async = MagicMock(side_effect=_profiler)
            elif idx == 1:
                async def _positioning(*a2, **kw2):
                    yield _make_text_event("analyzing...", thought=True)
                    yield _make_text_event(json.dumps(COMPETITIVE_PAYLOAD))
                r.run_async = MagicMock(side_effect=_positioning)
            else:
                r.run_async = MagicMock(side_effect=_empty_stream)

            client._runners.append(r)
            return r

        import backend.routers.web.capabilities as mod
        mod.Runner = MagicMock(side_effect=_make_runner)

        res = await client.post("/api/capabilities/competitive", json={"identity": IDENTITY_WITH_COMPETITORS})
        assert res.status_code == 200
        data = res.json()
        assert data["market_summary"] == "Bosphorus is positioned mid-market."
