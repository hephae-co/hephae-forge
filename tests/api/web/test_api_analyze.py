"""
Unit tests for POST /api/analyze (Margin Surgery pipeline).

Covers: input validation, fast-path vs slow-path, menu screenshot handling,
vision intake parsing, text-based menu fallback chain, surgeon output parsing,
score calculation, and binary blob stripping before DB writes.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers / Test Data
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

# Profile with NO screenshot — forces text fallback path
NO_SCREENSHOT_PROFILE = {
    "name": "Test Bistro",
    "address": "100 Main St",
    "officialUrl": "https://testbistro.com",
    "menuUrl": "https://testbistro.com/menu",
    "menuScreenshotBase64": None,
    "primaryColor": "#0f172a",
    "secondaryColor": "#334155",
    "persona": "Local Business",
}

SAMPLE_MENU_MARKDOWN = """
# Test Bistro Menu

## Burgers
- Classic Burger - $14.99
  Our signature half-pound beef patty with lettuce, tomato, and special sauce.
- Bacon Cheeseburger - $16.99
  Classic with crispy bacon and melted cheddar.

## Salads
- Caesar Salad - $11.99
  Romaine lettuce, croutons, parmesan, house-made dressing.
- Garden Salad - $9.99
  Mixed greens with seasonal vegetables.
"""


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
    """Standard client — screenshot mock returns base64, text fallback mocks return None."""
    mock_session_svc = MagicMock()
    mock_session_svc.create_session = AsyncMock(return_value=None)
    mock_session_svc.get_session = AsyncMock(return_value=MagicMock(state={}))

    runners_list = []

    def _make_runner(*a, **kw):
        r = MagicMock()
        r.run_async = MagicMock(side_effect=_empty_stream)
        runners_list.append(r)
        return r

    mock_scrape_text = AsyncMock(return_value=None)
    mock_search_text = AsyncMock(return_value=None)
    mock_extract_items = AsyncMock(return_value=[])

    with (
        patch("hephae_common.firebase.get_db", return_value=MagicMock()),
        patch("backend.routers.web.analyze.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.web.analyze.Runner", side_effect=_make_runner) as mock_runner_cls,
        patch("backend.routers.web.analyze.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/margin.html"),
        patch("backend.routers.web.analyze.build_margin_report", return_value="<html>margin</html>"),
        patch("backend.routers.web.analyze.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.web.analyze.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.analyze.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.analyze._scrape_menu_screenshot", new_callable=AsyncMock, return_value="/9j/4AAQSkZJRg=="),
        patch("backend.routers.web.analyze._scrape_menu_text", mock_scrape_text),
        patch("backend.routers.web.analyze._search_menu_text", mock_search_text),
        patch("backend.routers.web.analyze._extract_menu_items_from_text", mock_extract_items),
        patch("backend.routers.web.analyze.LocatorAgent") as mock_locator,
        patch("backend.routers.web.analyze.ProfilerAgent") as mock_profiler,
    ):
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
            ac._mock_scrape_text = mock_scrape_text  # type: ignore[attr-defined]
            ac._mock_search_text = mock_search_text  # type: ignore[attr-defined]
            ac._mock_extract_items = mock_extract_items  # type: ignore[attr-defined]
            yield ac


@pytest_asyncio.fixture
async def text_fallback_client():
    """Client where screenshot always fails but text fallback helpers can be configured per-test."""
    mock_session_svc = MagicMock()
    mock_session_svc.create_session = AsyncMock(return_value=None)
    mock_session_svc.get_session = AsyncMock(return_value=MagicMock(state={}))

    runners_list = []

    def _make_runner(*a, **kw):
        r = MagicMock()
        r.run_async = MagicMock(side_effect=_empty_stream)
        runners_list.append(r)
        return r

    # Text fallback mocks — configured per test via client attributes
    mock_scrape_text = AsyncMock(return_value=None)
    mock_find_menu = AsyncMock(return_value=None)
    mock_search_text = AsyncMock(return_value=None)
    mock_extract_items = AsyncMock(return_value=[])

    # Mock build_business_context to return an identity WITHOUT screenshot
    mock_ctx = MagicMock()
    mock_ctx.identity = {
        "name": "Test Bistro", "address": "100 Main St",
        "officialUrl": "https://testbistro.com",
        "menuUrl": "https://testbistro.com/menu",
        "primaryColor": "#0f172a", "secondaryColor": "#334155",
        "persona": "Local Business",
    }
    mock_ctx.get_cpi = MagicMock(return_value=None)
    mock_ctx.get_fred = MagicMock(return_value=None)
    mock_ctx.get_commodity_data = MagicMock(return_value=None)
    mock_ctx.commodity_prices = None

    with (
        patch("hephae_common.firebase.get_db", return_value=MagicMock()),
        patch("backend.routers.web.analyze.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.web.analyze.Runner", side_effect=_make_runner) as mock_runner_cls,
        patch("backend.routers.web.analyze.upload_report", new_callable=AsyncMock, return_value="https://cdn.hephae.co/reports/test/margin.html"),
        patch("backend.routers.web.analyze.build_margin_report", return_value="<html>margin</html>"),
        patch("backend.routers.web.analyze.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.web.analyze.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.analyze.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.analyze.build_business_context", new_callable=AsyncMock, return_value=mock_ctx),
        # Screenshot always fails
        patch("backend.routers.web.analyze._scrape_menu_screenshot", new_callable=AsyncMock, return_value=None),
        patch("backend.routers.web.analyze._download_screenshot_as_base64", new_callable=AsyncMock, return_value=None),
        # Text fallback mocks — accessible via client attributes
        patch("backend.routers.web.analyze._scrape_menu_text", mock_scrape_text),
        patch("backend.routers.web.analyze._find_menu_on_official_site", mock_find_menu),
        patch("backend.routers.web.analyze._search_menu_text", mock_search_text),
        patch("backend.routers.web.analyze._extract_menu_items_from_text", mock_extract_items),
        patch("backend.routers.web.analyze.LocatorAgent") as mock_locator,
        patch("backend.routers.web.analyze.ProfilerAgent") as mock_profiler,
    ):
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
            ac._mock_scrape_text = mock_scrape_text  # type: ignore[attr-defined]
            ac._mock_find_menu = mock_find_menu  # type: ignore[attr-defined]
            ac._mock_search_text = mock_search_text  # type: ignore[attr-defined]
            ac._mock_extract_items = mock_extract_items  # type: ignore[attr-defined]
            yield ac


def _configure_fast_mode_runners(client, vision_events=None, surgeon_events=None, advisor_events=None):
    """
    Pre-configure runners for a fast-mode pipeline with screenshot path.
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


def _configure_text_path_runners(client, surgeon_events=None, advisor_events=None):
    """
    Pre-configure runners for the text-fallback path (no vision runner).
    In text-fallback fast mode, the route creates runners in order:
      0: surgeon_runner
      1: advisor_runner
    """
    client._runners_list.clear()
    call_idx = {"n": 0}

    def _make_configured_runner(*a, **kw):
        r = MagicMock()
        idx = call_idx["n"]
        call_idx["n"] += 1

        events = None
        if idx == 0:
            events = surgeon_events
        elif idx == 1:
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
    async def test_menu_not_found_no_screenshot_no_url(self, client):
        """When no officialUrl, menuUrl, or screenshot is provided, slow path triggers -> menuNotFound."""
        profile = {**ENRICHED_PROFILE, "menuScreenshotBase64": None, "menuUrl": None, "officialUrl": None}
        res = await client.post("/api/analyze", json={"enrichedProfile": profile})
        # No officialUrl -> falls to slow path. All mocks return nothing -> menuNotFound
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True
        assert "message" in data

    @pytest.mark.asyncio
    async def test_fast_path_screenshots_official_url(self, client):
        """When menuUrl is missing but officialUrl exists, fast path screenshots officialUrl."""
        profile = {**ENRICHED_PROFILE, "menuScreenshotBase64": None, "menuUrl": None}
        res = await client.post("/api/analyze", json={"enrichedProfile": profile})
        # Screenshot succeeds (mock returns base64) but Vision returns nothing,
        # and text fallbacks also return nothing -> menuNotFound
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True
        assert "message" in data

    @pytest.mark.asyncio
    async def test_menu_not_found_no_menu_items_parsed(self, client):
        """Vision returns empty (no parsedMenuItems), text fallbacks all return nothing -> menuNotFound."""
        res = await client.post("/api/analyze", json={"enrichedProfile": ENRICHED_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True


# ---------------------------------------------------------------------------
# Screenshot path (vision-based extraction)
# ---------------------------------------------------------------------------

class TestScreenshotPath:
    @pytest.mark.asyncio
    async def test_score_from_leakage(self, client):
        """Full screenshot pipeline: vision → surgeon → advisor → score calculation."""
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
        assert data["reportUrl"] == "https://storage.googleapis.com/test/margin.html"

    @pytest.mark.asyncio
    async def test_report_url_in_response(self, client):
        """Response includes reportUrl from GCS upload."""
        vision_events = [_make_state_delta_event("parsedMenuItems", json.dumps(MENU_ITEMS))]
        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", "[]")]

        _configure_fast_mode_runners(client, vision_events, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": ENRICHED_PROFILE})
        assert res.status_code == 200
        assert "reportUrl" in res.json()

    @pytest.mark.asyncio
    async def test_identity_in_response(self, client):
        """Response includes identity with business details."""
        vision_events = [_make_state_delta_event("parsedMenuItems", json.dumps(MENU_ITEMS))]
        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", "[]")]

        _configure_fast_mode_runners(client, vision_events, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": ENRICHED_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["identity"]["name"] == "Test Bistro"
        # menuScreenshotBase64 should be in response identity (stripped only in DB write)
        assert "menuScreenshotBase64" in data["identity"]


# ---------------------------------------------------------------------------
# Text fallback path — menu URL crawl
# ---------------------------------------------------------------------------

class TestTextFallbackMenuCrawl:
    @pytest.mark.asyncio
    async def test_text_crawl_succeeds_from_menu_url(self, text_fallback_client):
        """No screenshot → text crawl of menuUrl succeeds → full pipeline completes."""
        client = text_fallback_client

        # Configure text fallback: crawl returns menu markdown
        client._mock_scrape_text.return_value = SAMPLE_MENU_MARKDOWN
        client._mock_extract_items.return_value = MENU_ITEMS

        # Configure runners for text path (no vision runner)
        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", json.dumps(["Raise prices."]))]
        _configure_text_path_runners(client, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert len(data["menu_items"]) == 2
        assert data["overall_score"] == 99

        # Verify _scrape_menu_text was called with the menuUrl
        client._mock_scrape_text.assert_called()
        first_call_url = client._mock_scrape_text.call_args_list[0][0][0]
        assert "testbistro.com/menu" in first_call_url

    @pytest.mark.asyncio
    async def test_text_crawl_falls_through_to_official_site_menu_finder(self, text_fallback_client):
        """menuUrl crawl returns None, but _find_menu_on_official_site succeeds."""
        client = text_fallback_client

        # menuUrl crawl returns None
        client._mock_scrape_text.return_value = None
        # _find_menu_on_official_site returns menu text
        client._mock_find_menu.return_value = SAMPLE_MENU_MARKDOWN
        client._mock_extract_items.return_value = MENU_ITEMS

        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", "[]")]
        _configure_text_path_runners(client, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200

        # _scrape_menu_text called once for menuUrl, _find_menu_on_official_site called for officialUrl
        client._mock_scrape_text.assert_called_once()
        client._mock_find_menu.assert_called_once_with("https://testbistro.com")

    @pytest.mark.asyncio
    async def test_text_crawl_returns_thin_content(self, text_fallback_client):
        """Crawl returns very short text (< threshold) — treated as failure, falls to Google search."""
        client = text_fallback_client

        # Both crawl attempts return None (content too thin is filtered in the real function)
        client._mock_scrape_text.return_value = None
        client._mock_find_menu.return_value = None
        # Google search also returns None
        client._mock_search_text.return_value = None

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True
        assert "message" in data


# ---------------------------------------------------------------------------
# Text fallback path — Google search
# ---------------------------------------------------------------------------

class TestTextFallbackGoogleSearch:
    @pytest.mark.asyncio
    async def test_google_search_succeeds(self, text_fallback_client):
        """Both crawl paths fail → Google search returns menu text → pipeline succeeds."""
        client = text_fallback_client

        # Crawl fails
        client._mock_scrape_text.return_value = None
        # Google search succeeds
        client._mock_search_text.return_value = SAMPLE_MENU_MARKDOWN
        client._mock_extract_items.return_value = MENU_ITEMS

        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", "[]")]
        _configure_text_path_runners(client, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert len(data["menu_items"]) == 2

        # Google search should have been called since crawls failed
        client._mock_search_text.assert_called_once_with("Test Bistro")

    @pytest.mark.asyncio
    async def test_google_search_fails_all_exhausted(self, text_fallback_client):
        """All fallback paths fail — returns menuNotFound."""
        client = text_fallback_client

        client._mock_scrape_text.return_value = None
        client._mock_find_menu.return_value = None
        client._mock_search_text.return_value = None

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True
        assert "message" in data


# ---------------------------------------------------------------------------
# Text fallback — LLM extraction returns empty
# ---------------------------------------------------------------------------

class TestTextFallbackExtractionFails:
    @pytest.mark.asyncio
    async def test_crawl_succeeds_but_extraction_empty(self, text_fallback_client):
        """Text is found but LLM can't extract items (e.g. non-menu page) → menuNotFound."""
        client = text_fallback_client

        client._mock_scrape_text.return_value = "Some random page content with no menu items"
        client._mock_extract_items.return_value = []  # LLM found nothing

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200
        data = res.json()
        assert data["menuNotFound"] is True

    @pytest.mark.asyncio
    async def test_extraction_called_with_business_name(self, text_fallback_client):
        """Verify _extract_menu_items_from_text receives the correct business name."""
        client = text_fallback_client

        client._mock_scrape_text.return_value = SAMPLE_MENU_MARKDOWN
        client._mock_extract_items.return_value = MENU_ITEMS

        surgeon_events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
        advisor_events = [_make_state_delta_event("strategicAdvice", "[]")]
        _configure_text_path_runners(client, surgeon_events, advisor_events)

        res = await client.post("/api/analyze", json={"enrichedProfile": NO_SCREENSHOT_PROFILE})
        assert res.status_code == 200

        client._mock_extract_items.assert_called_once_with(SAMPLE_MENU_MARKDOWN, "Test Bistro")


# ---------------------------------------------------------------------------
# Vision fails, text fallback succeeds (mixed path)
# ---------------------------------------------------------------------------

class TestVisionFailsTextSucceeds:
    @pytest.mark.asyncio
    async def test_vision_parse_fails_text_rescues(self, client):
        """
        Screenshot exists but vision returns garbage (unparseable) → text fallback kicks in.
        This simulates the real scenario: screenshot taken but OCR/vision fails.
        Uses the standard `client` fixture (screenshot mock returns base64).
        """
        profile_with_screenshot = {**ENRICHED_PROFILE}

        # Text fallback returns items when vision fails
        client._mock_scrape_text.return_value = SAMPLE_MENU_MARKDOWN
        client._mock_extract_items.return_value = MENU_ITEMS

        # Configure: vision runner emits parsedMenuItems with invalid JSON, then text path takes over
        # After text extraction, surgeon (idx 1) and advisor (idx 2)
        client._runners_list.clear()
        call_idx = {"n": 0}

        def _make_configured_runner(*a, **kw):
            r = MagicMock()
            idx = call_idx["n"]
            call_idx["n"] += 1

            if idx == 0:
                # Vision runner returns unparseable garbage
                events = [_make_state_delta_event("parsedMenuItems", "NOT VALID JSON {{{")]
                captured = list(events)
                async def _stream(*a2, **kw2):
                    for ev in captured:
                        yield ev
                r.run_async = MagicMock(side_effect=_stream)
            elif idx == 1:
                # Surgeon
                events = [_make_fn_response_event("perform_margin_surgery", MENU_ANALYSIS)]
                captured = list(events)
                async def _stream2(*a2, **kw2):
                    for ev in captured:
                        yield ev
                r.run_async = MagicMock(side_effect=_stream2)
            elif idx == 2:
                # Advisor
                events = [_make_state_delta_event("strategicAdvice", "[]")]
                captured = list(events)
                async def _stream3(*a2, **kw2):
                    for ev in captured:
                        yield ev
                r.run_async = MagicMock(side_effect=_stream3)
            else:
                r.run_async = MagicMock(side_effect=_empty_stream)

            client._runners_list.append(r)
            return r

        client._mock_runner_cls.side_effect = _make_configured_runner

        res = await client.post("/api/analyze", json={"enrichedProfile": profile_with_screenshot})
        assert res.status_code == 200
        data = res.json()
        assert len(data["menu_items"]) == 2

        # Verify text fallback was invoked
        client._mock_scrape_text.assert_called()
        client._mock_extract_items.assert_called()


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
        assert res.status_code in (200, 422)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestScrapeMenuText:
    """Unit tests for _scrape_menu_text helper."""

    @pytest.mark.asyncio
    async def test_returns_markdown_on_success(self):
        from backend.routers.web.analyze import _scrape_menu_text

        with patch(
            "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
            new_callable=AsyncMock,
            return_value={"markdown": SAMPLE_MENU_MARKDOWN},
        ):
            result = await _scrape_menu_text("https://example.com/menu")
            assert result is not None
            assert "Classic Burger" in result

    @pytest.mark.asyncio
    async def test_returns_none_on_short_content(self):
        from backend.routers.web.analyze import _scrape_menu_text

        with patch(
            "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
            new_callable=AsyncMock,
            return_value={"markdown": "Short"},
        ):
            result = await _scrape_menu_text("https://example.com/menu")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_crawl_error(self):
        from backend.routers.web.analyze import _scrape_menu_text

        with patch(
            "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await _scrape_menu_text("https://example.com/menu")
            assert result is None

    @pytest.mark.asyncio
    async def test_caps_at_15000_chars(self):
        from backend.routers.web.analyze import _scrape_menu_text

        long_text = "A" * 20000
        with patch(
            "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
            new_callable=AsyncMock,
            return_value={"markdown": long_text},
        ):
            result = await _scrape_menu_text("https://example.com/menu")
            assert result is not None
            assert len(result) == 15000


class TestSearchMenuText:
    """Unit tests for _search_menu_text helper."""

    @pytest.mark.asyncio
    async def test_returns_text_from_yelp(self):
        from backend.routers.web.analyze import _search_menu_text

        search_result = {
            "result": "Some summary",
            "sources": [
                {"url": "https://www.yelp.com/menu/test-bistro", "title": "Test Bistro Menu"},
            ],
        }
        with (
            patch("hephae_capabilities.shared_tools.google_search.google_search", new_callable=AsyncMock, return_value=search_result),
            patch(
                "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
                new_callable=AsyncMock,
                return_value={"markdown": SAMPLE_MENU_MARKDOWN},
            ),
        ):
            result = await _search_menu_text("Test Bistro")
            assert result is not None
            assert "Classic Burger" in result

    @pytest.mark.asyncio
    async def test_falls_through_to_any_source(self):
        from backend.routers.web.analyze import _search_menu_text

        search_result = {
            "result": "Some text",
            "sources": [
                {"url": "https://randomsite.com/test-bistro-menu", "title": "Menu"},
            ],
        }
        with (
            patch("hephae_capabilities.shared_tools.google_search.google_search", new_callable=AsyncMock, return_value=search_result),
            patch(
                "hephae_capabilities.shared_tools.crawl4ai.crawl_with_options",
                new_callable=AsyncMock,
                return_value={"markdown": SAMPLE_MENU_MARKDOWN},
            ),
        ):
            result = await _search_menu_text("Test Bistro")
            assert result is not None

    @pytest.mark.asyncio
    async def test_returns_search_text_as_last_resort(self):
        from backend.routers.web.analyze import _search_menu_text

        long_result_text = "Burger $14.99, Salad $11.99 " * 20  # > 200 chars
        search_result = {
            "result": long_result_text,
            "sources": [],  # No sources to crawl
        }
        with patch("hephae_capabilities.shared_tools.google_search.google_search", new_callable=AsyncMock, return_value=search_result):
            result = await _search_menu_text("Test Bistro")
            assert result is not None
            assert "Burger" in result

    @pytest.mark.asyncio
    async def test_returns_none_on_search_error(self):
        from backend.routers.web.analyze import _search_menu_text

        with patch(
            "hephae_capabilities.shared_tools.google_search.google_search",
            new_callable=AsyncMock,
            return_value={"error": "Search failed."},
        ):
            result = await _search_menu_text("Test Bistro")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_results(self):
        from backend.routers.web.analyze import _search_menu_text

        with patch(
            "hephae_capabilities.shared_tools.google_search.google_search",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await _search_menu_text("Test Bistro")
            assert result is None


class TestExtractMenuItemsFromText:
    """Unit tests for _extract_menu_items_from_text helper."""

    @pytest.mark.asyncio
    async def test_extracts_items_successfully(self):
        from backend.routers.web.analyze import _extract_menu_items_from_text

        mock_response = MagicMock()
        mock_response.text = json.dumps(MENU_ITEMS)

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("hephae_common.model_fallback.generate_with_fallback", new_callable=AsyncMock, return_value=mock_response),
            patch("google.genai.Client"),
        ):
            items = await _extract_menu_items_from_text(SAMPLE_MENU_MARKDOWN, "Test Bistro")
            assert len(items) == 2
            assert items[0]["item_name"] == "Classic Burger"

    @pytest.mark.asyncio
    async def test_returns_empty_without_api_key(self):
        from backend.routers.web.analyze import _extract_menu_items_from_text

        with patch.dict("os.environ", {}, clear=True):
            items = await _extract_menu_items_from_text(SAMPLE_MENU_MARKDOWN, "Test Bistro")
            assert items == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_error(self):
        from backend.routers.web.analyze import _extract_menu_items_from_text

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("hephae_common.model_fallback.generate_with_fallback", new_callable=AsyncMock, side_effect=Exception("Rate limited")),
            patch("google.genai.Client"),
        ):
            items = await _extract_menu_items_from_text(SAMPLE_MENU_MARKDOWN, "Test Bistro")
            assert items == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_invalid_json(self):
        from backend.routers.web.analyze import _extract_menu_items_from_text

        mock_response = MagicMock()
        mock_response.text = "Not valid JSON at all"

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("hephae_common.model_fallback.generate_with_fallback", new_callable=AsyncMock, return_value=mock_response),
            patch("google.genai.Client"),
        ):
            items = await _extract_menu_items_from_text(SAMPLE_MENU_MARKDOWN, "Test Bistro")
            assert items == []

    @pytest.mark.asyncio
    async def test_handles_markdown_fenced_json(self):
        from backend.routers.web.analyze import _extract_menu_items_from_text

        mock_response = MagicMock()
        mock_response.text = f"```json\n{json.dumps(MENU_ITEMS)}\n```"

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("hephae_common.model_fallback.generate_with_fallback", new_callable=AsyncMock, return_value=mock_response),
            patch("google.genai.Client"),
        ):
            items = await _extract_menu_items_from_text(SAMPLE_MENU_MARKDOWN, "Test Bistro")
            assert len(items) == 2
