"""
Crawl4aiTool — calls crawl4ai Docker REST API for markdown extraction.

Gracefully degrades: returns `{ error }` if crawl4ai service is down.
Content is truncated to avoid session state bloat.
Port of src/agents/tools/crawl4aiTool.ts.

Functions:
  crawl_for_content     — basic single-page markdown extraction (10K)
  crawl_with_options    — advanced single-page: JS exec, wait_for, CSS selector, overlays, iframes (15K)
  crawl_multiple_pages  — deep BFS crawl following internal links
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://localhost:11235")
MAX_CONTENT_LENGTH = 10_000
MAX_ADVANCED_CONTENT_LENGTH = 15_000
MAX_PAGE_CONTENT_LENGTH = 3_000

# Cache for identity token (valid ~1h, refresh when needed)
_cached_id_token: str | None = None
_token_expiry: float = 0


def _get_auth_headers() -> dict[str, str]:
    """Get authorization headers for Cloud Run service-to-service auth.

    Uses metadata server when running on GCP, skips for localhost.
    """
    global _cached_id_token, _token_expiry

    url = CRAWL4AI_URL
    if "localhost" in url or "127.0.0.1" in url:
        return {}

    # Return cached token if still valid (with 60s buffer)
    if _cached_id_token and time.monotonic() < _token_expiry - 60:
        return {"Authorization": f"Bearer {_cached_id_token}"}

    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(request, url)
        _cached_id_token = token
        _token_expiry = time.monotonic() + 3600  # ~1h validity
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        logger.warning(f"[Crawl4ai] Failed to get identity token: {e}")
        return {}


def _record_crawl_telemetry(
    url: str,
    strategy: str,
    success: bool,
    content_length: int = 0,
    duration_ms: int = 0,
) -> None:
    """Fire-and-forget crawl telemetry to BigQuery. Non-blocking, never raises."""
    try:
        import asyncio
        from hephae_db.bigquery.feedback import record_crawl_feedback

        # Extract a slug-like identifier from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        slug = parsed.netloc.replace("www.", "").replace(".", "-")

        asyncio.create_task(record_crawl_feedback(
            business_slug=slug,
            url=url,
            crawl_strategy=strategy,
            crawl_success=success,
            crawl_content_length=content_length,
            crawl_duration_ms=duration_ms,
        ))
    except Exception:
        pass  # Telemetry must never break crawling


async def crawl_for_content(
    url: str,
    extraction_query: Optional[str] = None,
) -> dict[str, Any]:
    """
    Use crawl4ai to extract clean markdown content, links, and media from a web page.
    Returns structured markdown suitable for LLM analysis.
    Gracefully returns an error if the crawl4ai service is unavailable.

    Args:
        url: The full URL to crawl (e.g. https://example.com).
        extraction_query: Optional specific content to focus on extracting.

    Returns:
        dict with 'markdown', 'links', 'media' keys, or 'error' on failure.
    """
    t0 = time.monotonic()
    try:
        logger.info(f"[Crawl4aiTool] Crawling {url} via crawl4ai...")

        body: dict[str, Any] = {
            "urls": [url],
            "priority": 5,
        }

        if extraction_query:
            body["extraction_config"] = {
                "type": "llm",
                "params": {"instruction": extraction_query},
            }

        auth_headers = _get_auth_headers()
        async with httpx.AsyncClient(timeout=30.0, headers=auth_headers) as client:
            res = await client.post(
                f"{CRAWL4AI_URL}/crawl",
                json=body,
            )

        if res.status_code != 200:
            text = res.text[:200]
            logger.warning(f"[Crawl4aiTool] crawl4ai returned {res.status_code}: {text}")
            _record_crawl_telemetry(url, "basic", False, 0, int((time.monotonic() - t0) * 1000))
            return {"error": f"crawl4ai returned HTTP {res.status_code}"}

        data = res.json()
        result = data[0] if isinstance(data, list) else data

        markdown = (
            result.get("markdown") or result.get("result", {}).get("markdown") or ""
        )[:MAX_CONTENT_LENGTH]

        links = (
            result.get("links") or result.get("result", {}).get("links") or []
        )[:100]

        media = (
            result.get("media") or result.get("result", {}).get("media") or []
        )[:50]

        logger.info(
            f"[Crawl4aiTool] Extracted {len(markdown)} chars markdown, {len(links)} links, {len(media)} media"
        )

        _record_crawl_telemetry(url, "basic", bool(markdown), len(markdown), int((time.monotonic() - t0) * 1000))
        return {"markdown": markdown, "links": links, "media": media}

    except httpx.TimeoutException:
        logger.warning("[Crawl4aiTool] Request timed out after 30s")
        _record_crawl_telemetry(url, "basic", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": "crawl4ai request timed out"}
    except Exception as error:
        logger.warning(f"[Crawl4aiTool] Service unavailable: {error}")
        _record_crawl_telemetry(url, "basic", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": f"crawl4ai unavailable: {error}"}


def _extract_result(data: Any) -> dict:
    """Unwrap crawl4ai response (list or dict) to a single result dict."""
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


def _extract_markdown(result: dict, max_len: int = MAX_CONTENT_LENGTH) -> str:
    """Pull markdown from result, checking nested .result if needed."""
    md = result.get("markdown") or result.get("result", {}).get("markdown") or ""
    return md[:max_len]


def _extract_links(result: dict, limit: int = 100) -> list:
    return (result.get("links") or result.get("result", {}).get("links") or [])[:limit]


def _extract_media(result: dict, limit: int = 50) -> list:
    return (result.get("media") or result.get("result", {}).get("media") or [])[:limit]


async def crawl_with_options(
    url: str,
    js_code: Optional[str] = None,
    wait_for: Optional[str] = None,
    css_selector: Optional[str] = None,
    remove_overlays: bool = True,
    scan_full_page: bool = False,
    process_iframes: bool = False,
) -> dict[str, Any]:
    """
    Advanced single-page crawl with browser control options.
    Use this when the basic crawl_for_content returns thin or incomplete content,
    or when the page requires JavaScript interaction, overlay removal, or iframe processing.

    Args:
        url: The full URL to crawl.
        js_code: JavaScript to execute before extraction (e.g. click buttons, dismiss popups).
        wait_for: CSS or JS wait condition (e.g. "css:article" or "js:() => document.querySelector('.loaded')").
        css_selector: Scope extraction to elements matching this CSS selector.
        remove_overlays: Remove cookie banners, popups, and modals before extraction.
        scan_full_page: Scroll through the entire page to trigger lazy-loaded content.
        process_iframes: Include content from iframes (menus are often embedded in iframes).

    Returns:
        dict with 'markdown', 'links', 'media' keys, or 'error' on failure.
    """
    t0 = time.monotonic()
    try:
        logger.info(f"[Crawl4aiAdvanced] Crawling {url} with options...")

        crawler_params: dict[str, Any] = {
            "cache_mode": "bypass",
            "page_timeout": 45000,
            "remove_overlay_elements": remove_overlays,
            "scan_full_page": scan_full_page,
            "process_iframes": process_iframes,
        }
        if js_code:
            crawler_params["js_code"] = js_code
        if wait_for:
            crawler_params["wait_for"] = wait_for
        if css_selector:
            crawler_params["css_selector"] = css_selector

        body: dict[str, Any] = {
            "urls": [url],
            "priority": 5,
            "crawler_config": {
                "type": "CrawlerRunConfig",
                "params": crawler_params,
            },
        }

        auth_headers = _get_auth_headers()
        async with httpx.AsyncClient(timeout=60.0, headers=auth_headers) as client:
            res = await client.post(f"{CRAWL4AI_URL}/crawl", json=body)

        if res.status_code != 200:
            text = res.text[:200]
            logger.warning(f"[Crawl4aiAdvanced] crawl4ai returned {res.status_code}: {text}")
            return {"error": f"crawl4ai returned HTTP {res.status_code}"}

        result = _extract_result(res.json())
        markdown = _extract_markdown(result, MAX_ADVANCED_CONTENT_LENGTH)
        links = _extract_links(result)
        media = _extract_media(result)

        logger.info(
            f"[Crawl4aiAdvanced] Extracted {len(markdown)} chars markdown, "
            f"{len(links)} links, {len(media)} media"
        )
        _record_crawl_telemetry(url, "advanced", bool(markdown), len(markdown), int((time.monotonic() - t0) * 1000))
        return {"markdown": markdown, "links": links, "media": media}

    except httpx.TimeoutException:
        logger.warning("[Crawl4aiAdvanced] Request timed out after 60s")
        _record_crawl_telemetry(url, "advanced", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": "crawl4ai advanced request timed out"}
    except Exception as error:
        logger.warning(f"[Crawl4aiAdvanced] Service unavailable: {error}")
        _record_crawl_telemetry(url, "advanced", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": f"crawl4ai unavailable: {error}"}


async def crawl_multiple_pages(
    url: str,
    max_pages: int = 10,
    max_depth: int = 2,
    url_pattern: Optional[str] = None,
) -> dict[str, Any]:
    """
    Deep crawl following internal links via BFS. Discovers all pages on a site
    up to max_pages and max_depth limits.

    Args:
        url: The starting URL for the deep crawl.
        max_pages: Maximum number of pages to crawl (default 10, prevents runaway).
        max_depth: BFS depth limit (default 2).
        url_pattern: Regex filter for which URLs to follow (e.g. "/menu|/food|/drink").

    Returns:
        dict with 'pages' array [{url, title, markdown}] and 'total_found', or 'error'.
    """
    t0 = time.monotonic()
    try:
        logger.info(f"[Crawl4aiDeep] Deep crawling {url} (max_pages={max_pages}, depth={max_depth})...")

        deep_crawl_params: dict[str, Any] = {
            "max_depth": max_depth,
            "max_pages": max_pages,
        }
        if url_pattern:
            deep_crawl_params["filter_pattern"] = url_pattern

        body: dict[str, Any] = {
            "urls": [url],
            "priority": 5,
            "crawler_config": {
                "type": "CrawlerRunConfig",
                "params": {
                    "cache_mode": "bypass",
                    "deep_crawl": {
                        "type": "BFSDeepCrawlStrategy",
                        "params": deep_crawl_params,
                    },
                },
            },
        }

        auth_headers = _get_auth_headers()
        async with httpx.AsyncClient(timeout=90.0, headers=auth_headers) as client:
            res = await client.post(f"{CRAWL4AI_URL}/crawl", json=body)

        if res.status_code != 200:
            text = res.text[:200]
            logger.warning(f"[Crawl4aiDeep] crawl4ai returned {res.status_code}: {text}")
            return {"error": f"crawl4ai returned HTTP {res.status_code}"}

        data = res.json()
        # Deep crawl returns a list of page results
        raw_pages = data if isinstance(data, list) else [data]

        pages = []
        for page in raw_pages:
            page_result = page if isinstance(page, dict) else {}
            page_url = page_result.get("url", url)
            page_title = (
                page_result.get("title")
                or page_result.get("result", {}).get("title")
                or ""
            )
            page_md = _extract_markdown(page_result, MAX_PAGE_CONTENT_LENGTH)
            pages.append({"url": page_url, "title": page_title, "markdown": page_md})

        total_content = sum(len(p.get("markdown", "")) for p in pages)
        logger.info(f"[Crawl4aiDeep] Found {len(pages)} pages from {url}")
        _record_crawl_telemetry(url, "deep", bool(pages), total_content, int((time.monotonic() - t0) * 1000))
        return {"pages": pages, "total_found": len(pages)}

    except httpx.TimeoutException:
        logger.warning("[Crawl4aiDeep] Request timed out after 90s")
        _record_crawl_telemetry(url, "deep", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": "crawl4ai deep crawl request timed out"}
    except Exception as error:
        logger.warning(f"[Crawl4aiDeep] Service unavailable: {error}")
        _record_crawl_telemetry(url, "deep", False, 0, int((time.monotonic() - t0) * 1000))
        return {"error": f"crawl4ai unavailable: {error}"}
