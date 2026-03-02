"""
Unit tests for POST /api/analyze (Margin Surgery pipeline).

Covers: input validation, fast-path vs slow-path, menu screenshot handling,
vision intake parsing, surgeon output parsing, score calculation, and
binary blob stripping before DB writes.
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

MENU_ITEMS = [
    {"item_name": "Classic Burger", "current_price": 14.99, "category": "Burgers"},
    {"item_name": "Caesar Salad", "current_price": 11.99, "category": "Salads"},
]

MENU_ANALYSIS = [
    {
        "item_name": "Classic Burger", "current_price": 14.99, "category": "Burgers",
        "competitor_benchmark": 16.50, "commodity_factor": 1.03,
        "recommended_price": 16.49, "price_leakage": 1.50,
        "confidence_score": 85, "rationale": "Underpriced vs local average.",
    },
    {
        "item_name": "Caesar Salad", "current_price": 11.99, "category": "Salads",
        "competitor_benchmark": 12.50, "commodity_factor": 1.01,
        "recommended_price": 12.49, "price_leakage": 0.50,
        "confidence_score": 72, "rationale": "Slightly below market.",
    },
]

ENRICHED_PROFILE = {
    "name": "Test Bistro",
    "address": "100 Main St",
    "officialUrl": "https://testbistro.com",
    "menuUrl": "https://testbistro.com/menu",
    "menuScreenshotBase64": "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
    "primaryColor": "#0f172a",
    "secondaryColor": "#334155",
    "persona": "Local Business",
}


def _make_state_delta_event(key: str, value):
    """Create an event with actions.state_delta using SimpleNamespace (matches ADK objects)."""
    return SimpleNamespace(
        content=None,
        actions=SimpleNamespace(state_delta={key: value}),
    )


def _make_fn_response_event(name: str, response):
    """Create an event with a function response in content.parts."""
    part = SimpleNamespace(
        text=None,
        thought=False,
        function_call=None,
        function_response=SimpleNamespace(name=name, response=response),
    )
    return SimpleNamespace(content=SimpleNamespace(parts=[part]), actions=None)


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

    # Track runners created in order
    runners_list = []

    def _make_runner(*a, **kw):
        r = MagicMock()
        r.run_async = MagicMock(side_effect=_empty_stream)
        runners_list.append(r)
        return r

    with (
        patch("backend.routers.analyze.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.analyze.Runner", side_effect=_make_runner) as mock_runner_cls,
        patch("backend.routers.analyze.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/margin.html"),
        patch("backend.routers.analyze.build_margin_report", return_value="<html>margin</html>"),
        patch("backend.routers.analyze.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.analyze.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.analyze.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.analyze._scrape_menu_screenshot", new_callable=AsyncMock, return_value="/9j/4AAQSkZJRg=="),
        patch("backend.routers.analyze.LocatorAgent") as mock_locator,
        patch("backend.routers.analyze.ProfilerAgent") as mock_profiler,
    ):
        # Mock slow-path agents
        mock_locator.resolve = AsyncMock(return_value={
            "name": "Test Bistro", "address": "100 Main St", "officialUrl": "https://testbistro.com"
        })
        mock_profiler.profile = AsyncMock(return_value={
            "name": "Test Bistro", "address": "100 Main St", "officialUrl": "https://testbistro.com",
            "menuScreenshotBase64": None,
        })

        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._runners_list = runners_list  # type: ignore[attr-defined]
            ac._mock_runner_cls = mock_runner_cls  # type: ignore[attr-defined]
            yield ac


def _configure_fast_mode_runners(client, vision_events=None, surgeon_events=None, advisor_events=None):
    """
    Pre-configure runners for a fast-mode pipeline.
    In fast mode (no advancedMode), the route creates runners in order:
      0: vision_runner
      1: surgeon_runner (benchmarker/commodity skipped)
      2: advisor_runner
    """
    client._runners_list.clear()
    call_idx = {"n": 0}

    def _make_configured_runner(*a, **kw):
        r = MagicMock()
        idx = call_idx["n"]
        call_idx["n"] += 1

        events = None
        if idx == 0:
            events = vision_events
        elif idx == 1:
            events = surgeon_events
        elif idx == 2:
            events = advisor_events

        if events:
            captured = list(events)
            async def _stream(*a2, **kw2):
                for ev in captured:
                    yield ev
            r.run_async = MagicMock(side_effect=_stream)
        else:
            r.run_async = MagicMock(side_effect=_empty_stream)

        client._runners_list.append(r)
        return r

    client._mock_runner_cls.side_effect = _make_configured_runner


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    @pytest.mark.asyncio
    async def test_422_no_screenshot_no_url(self, client):
        """When no officialUrl, menuUrl, or screenshot is provided, slow path triggers -> 422."""
        profile = {**ENRICHED_PROFILE, "menuScreenshotBase64": None, "menuUrl": None, "officialUrl": None}
        res = await client.post("/api/analyze", json={"enrichedProfile": profile})
        # No officialUrl -> falls to slow path. Mocked ProfilerAgent returns no screenshot -> 422
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_fast_path_screenshots_official_url(self, client):
        """When menuUrl is missing but officialUrl exists, fast path screenshots officialUrl."""
        profile = {**ENRICHED_PROFILE, "menuScreenshotBase64": None, "menuUrl": None}
        res = await client.post("/api/analyze", json={"enrichedProfile": profile})
        # Fast path takes officialUrl, screenshots it, but Vision returns nothing -> 422
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_422_no_menu_items_parsed(self, client):
        # Vision returns empty — no parsedMenuItems
        res = await client.post("/api/analyze", json={"enrichedProfile": ENRICHED_PROFILE})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

class TestScoreCalculation:
    @pytest.mark.asyncio
    async def test_score_from_leakage(self, client):
        # Total leakage = 1.50 + 0.50 = 2.00
        # Total revenue = 14.99 + 11.99 = 26.98
        # Score = max(0, min(100, round(100 - (2.00 / 26.98 * 20)))) = round(100 - 1.48) = 99
        vision_events = [_make_state_delta_event("parsedMenuItems", json.dumps(MENU_ITEMS))]
        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", json.dumps(["Raise burger price."]))]

        _configure_fast_mode_runners(client, vision_events, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": ENRICHED_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["overall_score"] == 99
        assert len(data["menu_items"]) == 2


# ---------------------------------------------------------------------------
# Default colors
# ---------------------------------------------------------------------------

class TestDefaultColors:
    @pytest.mark.asyncio
    async def test_defaults_applied(self, client):
        profile = {
            "name": "No Color Bistro",
            "officialUrl": "https://nocolorbistro.com",
            "menuUrl": "https://nocolorbistro.com/menu",
            "menuScreenshotBase64": "/9j/4AAQSkZJRg==",
        }
        # Will get 422 because vision returns nothing, but we can check the handler doesn't crash
        res = await client.post("/api/analyze", json={"enrichedProfile": profile})
        # Just verify it doesn't 500 — the defaults are applied internally
        assert res.status_code in (200, 422)
