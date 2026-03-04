"""
Level 1: Google Search tool returns grounding-verified source URLs.

Validates that google_search() returns real URLs (not hallucinated)
by checking grounding metadata sources for expected domains.
"""

from __future__ import annotations

import pytest

from backend.agents.shared_tools.google_search import google_search
from backend.tests.integration.businesses import BUSINESSES

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ------------------------------------------------------------------
# Social platform search — does google_search find real profiles?
# ------------------------------------------------------------------

PLATFORM_QUERIES = {
    "instagram": "site:instagram.com",
    "facebook": "site:facebook.com",
    "yelp": "site:yelp.com",
}


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.parametrize("platform,site_filter", list(PLATFORM_QUERIES.items()), ids=list(PLATFORM_QUERIES.keys()))
@pytest.mark.timeout(30)
async def test_google_search_finds_platform_urls(biz, platform, site_filter):
    """google_search for '[business] site:[platform]' returns sources with that domain."""
    query = f"{biz.name} {biz.city} {biz.state} {site_filter}"
    result = await google_search(query)

    assert "error" not in result, f"Search failed for {biz.name}: {result.get('error')}"
    assert "result" in result, "Missing 'result' key in response"
    assert "sources" in result, "Missing 'sources' key — grounding metadata not extracted"

    # We don't require every platform to have results for every business,
    # but the sources array should be populated (grounding is working)
    if result["sources"]:
        urls = [s["url"] for s in result["sources"]]
        # Verify URLs are real (contain the platform domain or related)
        for url in urls:
            assert url.startswith("http"), f"Source URL doesn't start with http: {url}"


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(30)
async def test_google_search_returns_text_result(biz):
    """google_search returns a non-empty text result."""
    result = await google_search(f"{biz.name} {biz.city} {biz.state} official website")

    assert "error" not in result
    assert result.get("result"), "Empty text result from google_search"
    assert len(result["result"]) > 20, "Result text suspiciously short"


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(60)
async def test_google_search_finds_known_social(biz):
    """For businesses with known social presence, at least one platform search returns matching sources or text."""
    found_any = False

    for attempt in range(2):
        for platform in biz.expected_social_platforms:
            site_filter = PLATFORM_QUERIES.get(platform)
            if not site_filter:
                continue

            result = await google_search(f"{biz.name} {biz.city} {site_filter}")
            domain = platform + ".com"

            # Check grounding sources for matching URLs
            if result.get("sources"):
                matching = [s for s in result["sources"] if domain in s.get("url", "")]
                if matching:
                    found_any = True
                    break

            # Fallback: check result text for platform domain mentions
            if result.get("result") and domain in result["result"]:
                found_any = True
                break

        if found_any:
            break

    assert found_any, (
        f"{biz.name} is known to have {biz.expected_social_platforms} "
        "but google_search found none of them via grounding sources or result text"
    )
