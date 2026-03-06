"""Unit tests for the screenshot_page shared tool (mock Playwright)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.shared_tools.playwright import screenshot_page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_playwright(
    screenshot_bytes: bytes = b"fake-jpeg-data",
    html_content: str = "<html><body>Hello</body></html>",
    goto_side_effect=None,
    screenshot_side_effect=None,
):
    """Build a mock Playwright stack: pw -> browser -> context -> page."""
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=goto_side_effect)
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock(
        return_value=screenshot_bytes,
        side_effect=screenshot_side_effect,
    )
    page.content = AsyncMock(return_value=html_content)

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    pw = AsyncMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    async_pw = AsyncMock()
    async_pw.__aenter__ = AsyncMock(return_value=pw)
    async_pw.__aexit__ = AsyncMock(return_value=None)

    return async_pw, page, browser


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScreenshotPage:
    @pytest.mark.asyncio
    async def test_returns_base64_screenshot(self):
        raw_bytes = b"\xff\xd8\xff\xe0fake-jpeg"
        mock_pw, page, _ = _mock_playwright(screenshot_bytes=raw_bytes)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await screenshot_page("https://example.com/menu")

        assert result["error"] is None
        assert result["screenshot_base64"] == base64.b64encode(raw_bytes).decode()

    @pytest.mark.asyncio
    async def test_returns_html_content(self):
        html = "<html><body><h1>Menu</h1></body></html>"
        mock_pw, page, _ = _mock_playwright(html_content=html)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await screenshot_page("https://example.com/menu")

        assert result["html"] == html
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_handles_navigation_failure(self):
        mock_pw, page, _ = _mock_playwright(
            goto_side_effect=Exception("net::ERR_CONNECTION_REFUSED"),
        )

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await screenshot_page("https://unreachable.example.com")

        assert result["screenshot_base64"] == ""
        assert result["html"] == ""
        assert "ERR_CONNECTION_REFUSED" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_screenshot_failure(self):
        mock_pw, page, _ = _mock_playwright(
            screenshot_side_effect=Exception("Screenshot timed out"),
        )

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await screenshot_page("https://example.com")

        assert result["screenshot_base64"] == ""
        assert "Screenshot timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_custom_quality_passed_to_screenshot(self):
        mock_pw, page, _ = _mock_playwright()

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            await screenshot_page("https://example.com", quality=80)

        page.screenshot.assert_called_once_with(full_page=True, type="jpeg", quality=80)

    @pytest.mark.asyncio
    async def test_custom_wait_seconds(self):
        mock_pw, page, _ = _mock_playwright()

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            await screenshot_page("https://example.com", wait_seconds=3.5)

        page.wait_for_timeout.assert_called_once_with(3500)

    @pytest.mark.asyncio
    async def test_browser_closed_on_success(self):
        mock_pw, _, browser = _mock_playwright()

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            await screenshot_page("https://example.com")

        browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_closed_on_failure(self):
        mock_pw, _, browser = _mock_playwright(
            goto_side_effect=Exception("fail"),
        )

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            await screenshot_page("https://example.com")

        browser.close.assert_called_once()
