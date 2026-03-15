"""Unit tests for crawl4ai shared tool functions (mock httpx)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from hephae_agents.shared_tools.crawl4ai import (
    crawl_for_content,
    crawl_with_options,
    crawl_multiple_pages,
    MAX_CONTENT_LENGTH,
    MAX_ADVANCED_CONTENT_LENGTH,
    MAX_PAGE_CONTENT_LENGTH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int = 200, json_data=None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text or json.dumps(json_data or {})
    return resp


def _mock_client(response):
    """Create mock httpx.AsyncClient that returns the given response on POST."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ============================================================================
# crawl_with_options tests
# ============================================================================

class TestCrawlWithOptions:
    @pytest.mark.asyncio
    async def test_returns_markdown_links_media(self):
        data = {
            "markdown": "# Hello World",
            "links": [{"href": "https://a.com"}],
            "media": [{"src": "img.jpg"}],
        }
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert result["markdown"] == "# Hello World"
        assert len(result["links"]) == 1
        assert len(result["media"]) == 1

    @pytest.mark.asyncio
    async def test_passes_js_code_in_request(self):
        resp = _mock_response(200, {"markdown": "ok"})
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_with_options("https://example.com", js_code="window.scrollTo(0,500);")

        call_args = client.post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["crawler_config"]["params"]["js_code"] == "window.scrollTo(0,500);"

    @pytest.mark.asyncio
    async def test_passes_wait_for_selector(self):
        resp = _mock_response(200, {"markdown": "ok"})
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_with_options("https://example.com", wait_for="css:header")

        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json")
        assert body["crawler_config"]["params"]["wait_for"] == "css:header"

    @pytest.mark.asyncio
    async def test_passes_css_selector(self):
        resp = _mock_response(200, {"markdown": "ok"})
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_with_options("https://example.com", css_selector="main")

        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json")
        assert body["crawler_config"]["params"]["css_selector"] == "main"

    @pytest.mark.asyncio
    async def test_passes_scan_full_page_and_iframes(self):
        resp = _mock_response(200, {"markdown": "ok"})
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_with_options("https://example.com", scan_full_page=True, process_iframes=True)

        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json")
        params = body["crawler_config"]["params"]
        assert params["scan_full_page"] is True
        assert params["process_iframes"] is True

    @pytest.mark.asyncio
    async def test_truncates_markdown_to_15k(self):
        long_md = "x" * 20_000
        resp = _mock_response(200, {"markdown": long_md})
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert len(result["markdown"]) == MAX_ADVANCED_CONTENT_LENGTH

    @pytest.mark.asyncio
    async def test_graceful_on_timeout(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert "error" in result
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_graceful_on_http_error(self):
        resp = _mock_response(500, text="Internal Server Error")
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert "error" in result
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_graceful_on_service_down(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=ConnectionRefusedError("refused"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert "error" in result
        assert "unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_list_response(self):
        """crawl4ai sometimes returns a list of results."""
        data = [{"markdown": "# From List", "links": [], "media": []}]
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert result["markdown"] == "# From List"

    @pytest.mark.asyncio
    async def test_handles_nested_result(self):
        """Some crawl4ai versions nest under .result key."""
        data = {"result": {"markdown": "# Nested", "links": [{"x": 1}], "media": []}}
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_with_options("https://example.com")

        assert result["markdown"] == "# Nested"
        assert len(result["links"]) == 1


# ============================================================================
# crawl_multiple_pages tests
# ============================================================================

class TestCrawlMultiplePages:
    @pytest.mark.asyncio
    async def test_returns_pages_array(self):
        data = [
            {"url": "https://example.com", "title": "Home", "markdown": "# Home"},
            {"url": "https://example.com/about", "title": "About", "markdown": "# About"},
        ]
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_multiple_pages("https://example.com")

        assert "pages" in result
        assert len(result["pages"]) == 2
        assert result["total_found"] == 2
        assert result["pages"][0]["url"] == "https://example.com"
        assert result["pages"][1]["title"] == "About"

    @pytest.mark.asyncio
    async def test_passes_deep_crawl_config(self):
        resp = _mock_response(200, [])
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_multiple_pages("https://example.com", max_pages=5, max_depth=3)

        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json")
        deep = body["crawler_config"]["params"]["deep_crawl"]
        assert deep["type"] == "BFSDeepCrawlStrategy"
        assert deep["params"]["max_pages"] == 5
        assert deep["params"]["max_depth"] == 3

    @pytest.mark.asyncio
    async def test_passes_url_pattern_filter(self):
        resp = _mock_response(200, [])
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            await crawl_multiple_pages("https://example.com", url_pattern="/menu|/food")

        body = client.post.call_args.kwargs.get("json") or client.post.call_args[1].get("json")
        deep = body["crawler_config"]["params"]["deep_crawl"]
        assert deep["params"]["filter_pattern"] == "/menu|/food"

    @pytest.mark.asyncio
    async def test_truncates_per_page_markdown(self):
        long_md = "x" * 5000
        data = [{"url": "https://example.com", "title": "Home", "markdown": long_md}]
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_multiple_pages("https://example.com")

        assert len(result["pages"][0]["markdown"]) == MAX_PAGE_CONTENT_LENGTH

    @pytest.mark.asyncio
    async def test_graceful_on_timeout(self):
        client = AsyncMock()
        client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_multiple_pages("https://example.com")

        assert "error" in result
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_graceful_on_empty_response(self):
        resp = _mock_response(200, [])
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_multiple_pages("https://example.com")

        assert result["pages"] == []
        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_handles_single_dict_response(self):
        """Some responses come as a single dict instead of list."""
        data = {"url": "https://example.com", "title": "Home", "markdown": "# Home"}
        resp = _mock_response(200, data)
        client = _mock_client(resp)

        with patch("hephae_agents.shared_tools.crawl4ai.httpx.AsyncClient", return_value=client):
            result = await crawl_multiple_pages("https://example.com")

        assert len(result["pages"]) == 1
        assert result["pages"][0]["title"] == "Home"
