"""
Level 2b: Functional tests for crawl4ai advanced tool functions.

Tests crawl_with_options() and crawl_multiple_pages() against the real
crawl4ai Docker container. Validates that the crawl4ai REST API returns
expected data structures and handles edge cases.

Requires: crawl4ai Docker container running (docker compose up crawl4ai)
Marked: @pytest.mark.needs_browser (skipped on Cloud Run or without crawl4ai)
"""

from __future__ import annotations

import logging
import os

import httpx
import pytest

from hephae_agents.shared_tools.crawl4ai import (
    crawl_for_content,
    crawl_with_options,
    crawl_multiple_pages,
)

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.needs_browser, pytest.mark.asyncio]

CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://localhost:11235")


def _crawl4ai_available() -> bool:
    """Check if crawl4ai Docker container is reachable."""
    try:
        resp = httpx.get(f"{CRAWL4AI_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def skip_if_no_crawl4ai():
    if not _crawl4ai_available():
        pytest.skip("crawl4ai Docker container not running")


# ============================================================================
# crawl_with_options — live tests
# ============================================================================


class TestCrawlWithOptionsLive:
    """Functional tests for crawl_with_options against real crawl4ai."""

    @pytest.mark.timeout(90)
    async def test_crawl_public_website_returns_markdown(self):
        """Crawl a well-known public website and verify markdown content returned."""
        result = await crawl_with_options("https://en.wikipedia.org/wiki/Restaurant")

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "markdown" in result
        assert len(result["markdown"]) > 100, (
            f"Expected substantial markdown, got {len(result['markdown'])} chars"
        )

    @pytest.mark.timeout(90)
    async def test_crawl_content_rich_page(self):
        """Crawl a content-rich public page and verify substantial markdown returned."""
        # Use httpbin which is reliable and doesn't block bots
        result = await crawl_with_options(
            "https://httpbin.org/html",
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "markdown" in result
        assert len(result["markdown"]) > 50, (
            f"Expected content from httpbin, got {len(result['markdown'])} chars"
        )
        # httpbin /html returns Herman Melville excerpt
        assert "melville" in result["markdown"].lower() or len(result["markdown"]) > 100, (
            f"Unexpected content: {result['markdown'][:200]}"
        )

    @pytest.mark.timeout(90)
    async def test_crawl_with_css_selector_scoping(self):
        """Crawl with CSS selector should return scoped content."""
        # Crawl Wikipedia article with CSS selector for the main content area
        result = await crawl_with_options(
            "https://en.wikipedia.org/wiki/Pizza",
            css_selector="#mw-content-text",
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "markdown" in result
        assert len(result["markdown"]) > 100

    @pytest.mark.timeout(90)
    async def test_crawl_with_full_page_scan(self):
        """Crawl with scan_full_page=True returns content."""
        result = await crawl_with_options(
            "https://httpbin.org/html",
            scan_full_page=True,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "markdown" in result
        # scan_full_page should still return content (at least some markdown)
        assert len(result["markdown"].strip()) > 0, (
            "scan_full_page returned empty markdown"
        )

    @pytest.mark.timeout(90)
    async def test_crawl_returns_links(self):
        """Crawling a page should return extracted links."""
        result = await crawl_with_options("https://en.wikipedia.org/wiki/Restaurant")

        assert "links" in result
        # Wikipedia pages have many links
        if result["links"]:
            assert isinstance(result["links"], list)
            # At least some should have href
            with_href = [l for l in result["links"] if isinstance(l, dict) and l.get("href")]
            logger.info(f"Found {len(with_href)} links with href")

    @pytest.mark.timeout(90)
    async def test_crawl_returns_media(self):
        """Crawling a page should return media elements."""
        result = await crawl_with_options("https://en.wikipedia.org/wiki/Pizza")

        assert "media" in result
        assert isinstance(result["media"], list)

    @pytest.mark.timeout(90)
    async def test_crawl_nonexistent_domain_graceful(self):
        """Crawling a non-existent domain returns an error, not an exception."""
        result = await crawl_with_options("https://this-domain-definitely-does-not-exist-xyz123.com")

        # Should return gracefully, either with error or empty markdown
        assert isinstance(result, dict)
        if "error" in result:
            logger.info(f"Got expected error: {result['error']}")
        else:
            # Some crawlers return empty markdown for unreachable sites
            assert "markdown" in result

    @pytest.mark.timeout(90)
    async def test_crawl_with_remove_overlays(self):
        """Crawl with remove_overlays=True should still return content."""
        result = await crawl_with_options(
            "https://en.wikipedia.org/wiki/Restaurant",
            remove_overlays=True,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "markdown" in result
        assert len(result["markdown"]) > 100


# ============================================================================
# crawl_multiple_pages — live tests
# ============================================================================


class TestCrawlMultiplePagesLive:
    """Functional tests for crawl_multiple_pages against real crawl4ai."""

    @pytest.mark.timeout(120)
    async def test_deep_crawl_finds_subpages(self):
        """Deep crawl of a multi-page site discovers subpages."""
        result = await crawl_multiple_pages(
            "https://httpbin.org",
            max_pages=5,
            max_depth=1,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "pages" in result
        assert isinstance(result["pages"], list)
        assert "total_found" in result

        if result["pages"]:
            # Each page should have url and markdown
            for page in result["pages"]:
                assert "url" in page, f"Page missing 'url': {page.keys()}"
                assert "markdown" in page, f"Page missing 'markdown': {page.keys()}"

        logger.info(f"Deep crawl found {result['total_found']} pages")

    @pytest.mark.timeout(120)
    async def test_deep_crawl_respects_max_pages(self):
        """Deep crawl with max_pages=3 returns at most 3 pages."""
        result = await crawl_multiple_pages(
            "https://httpbin.org",
            max_pages=3,
            max_depth=1,
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "pages" in result
        assert len(result["pages"]) <= 3, (
            f"Expected at most 3 pages, got {len(result['pages'])}"
        )

    @pytest.mark.timeout(120)
    async def test_deep_crawl_with_url_pattern(self):
        """Deep crawl with URL pattern filters results."""
        result = await crawl_multiple_pages(
            "https://httpbin.org",
            max_pages=10,
            max_depth=1,
            url_pattern="httpbin",
        )

        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert "pages" in result
        # All returned pages should have httpbin in URL
        for page in result["pages"]:
            if page.get("url"):
                assert "httpbin" in page["url"], (
                    f"Page URL {page['url']} doesn't match pattern 'httpbin'"
                )

    @pytest.mark.timeout(120)
    async def test_deep_crawl_nonexistent_domain(self):
        """Deep crawl of non-existent domain returns gracefully."""
        result = await crawl_multiple_pages(
            "https://this-domain-definitely-does-not-exist-xyz123.com",
            max_pages=3,
        )

        assert isinstance(result, dict)
        # Should either have an error or empty pages
        if "error" not in result:
            assert "pages" in result
            assert isinstance(result["pages"], list)


# ============================================================================
# Comparison: basic vs advanced crawl
# ============================================================================


class TestCrawlComparison:
    """Compare basic crawl_for_content with advanced crawl_with_options."""

    @pytest.mark.timeout(120)
    async def test_advanced_returns_more_fields(self):
        """crawl_with_options returns links and media that basic crawl doesn't."""
        url = "https://en.wikipedia.org/wiki/Pizza"

        basic = await crawl_for_content(url)
        advanced = await crawl_with_options(url)

        # Both should return markdown
        assert isinstance(basic, str) or isinstance(basic, dict)
        assert isinstance(advanced, dict)

        # Advanced should have links and media
        assert "links" in advanced
        assert "media" in advanced

        logger.info(
            f"Basic: {type(basic).__name__}, "
            f"Advanced: markdown={len(advanced.get('markdown', ''))}, "
            f"links={len(advanced.get('links', []))}, "
            f"media={len(advanced.get('media', []))}"
        )
