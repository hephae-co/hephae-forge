"""Shared tool: URL validation via pattern matching + HTTP reachability check."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform URL patterns
# ---------------------------------------------------------------------------

PLATFORM_PATTERNS: dict[str, re.Pattern[str]] = {
    "instagram":   re.compile(r"https?://(www\.)?instagram\.com/[A-Za-z0-9_.]+/?"),
    "facebook":    re.compile(r"https?://(www\.|m\.)?facebook\.com/[A-Za-z0-9_./-]+/?"),
    "twitter":     re.compile(r"https?://(www\.)?(twitter\.com|x\.com)/[A-Za-z0-9_]+/?"),
    "tiktok":      re.compile(r"https?://(www\.)?tiktok\.com/@[A-Za-z0-9_.]+/?"),
    "yelp":        re.compile(r"https?://(www\.)?yelp\.com/biz/[a-z0-9-]+"),
    "grubhub":     re.compile(r"https?://(www\.)?grubhub\.com/restaurant/[a-z0-9-]+"),
    "doordash":    re.compile(r"https?://(www\.)?doordash\.com/store/[a-z0-9-]+"),
    "ubereats":    re.compile(r"https?://(www\.)?ubereats\.com/store/[a-z0-9-]+"),
    "seamless":    re.compile(r"https?://(www\.)?seamless\.com/menu/[a-z0-9-]+"),
    "toasttab":    re.compile(r"https?://(www\.)?toasttab\.com/[a-z0-9-]+"),
    "google_maps": re.compile(
        r"https?://(www\.)?google\.com/maps/place/|https?://maps\.google\.com/"
    ),
}

# Platforms that commonly return 403 for automated HEAD/GET requests
SOCIAL_403_PLATFORMS = {"instagram", "tiktok", "facebook", "twitter"}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT = 5.0  # seconds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_pattern(url: str, platform: str) -> bool:
    """Return True if *url* matches the expected pattern for *platform*."""
    pattern = PLATFORM_PATTERNS.get(platform)
    if pattern is None:
        return True  # unknown platform → skip pattern check
    return bool(pattern.match(url))


async def _http_check(url: str) -> tuple[int | None, str | None]:
    """HEAD then GET with follow-redirects. Returns (status_code, final_url)."""
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.head(url)
            # Some servers reject HEAD — retry with GET
            if resp.status_code == 405:
                resp = await client.get(url)
            final_url = str(resp.url) if str(resp.url) != url else None
            return resp.status_code, final_url
    except httpx.TimeoutException:
        return None, None
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Public tool (registered as FunctionTool for ADK agents)
# ---------------------------------------------------------------------------


async def validate_url(url: str, expected_platform: str = "") -> dict:
    """Validate a URL via pattern matching and HTTP reachability check.

    Args:
        url: The full URL to validate (e.g. https://instagram.com/bosphorus_nj).
        expected_platform: Optional platform hint for pattern validation.
            One of: instagram, facebook, twitter, tiktok, yelp, grubhub,
            doordash, ubereats, seamless, toasttab, google_maps, or empty.

    Returns:
        dict with keys: url, status, http_code, redirected_to, pattern_ok, reason.
        status is one of: "valid", "invalid", "unverifiable", "pattern_mismatch".
    """
    if not url or not isinstance(url, str):
        return {
            "url": url or "",
            "status": "invalid",
            "http_code": None,
            "redirected_to": None,
            "pattern_ok": False,
            "reason": "Empty or non-string URL",
        }

    url = url.strip()
    platform = expected_platform.strip().lower()

    # Step 1: pattern check
    pattern_ok = _check_pattern(url, platform)
    if not pattern_ok:
        return {
            "url": url,
            "status": "pattern_mismatch",
            "http_code": None,
            "redirected_to": None,
            "pattern_ok": False,
            "reason": f"URL does not match expected {platform} pattern",
        }

    # Step 2: HTTP reachability
    status_code, final_url = await _http_check(url)

    if status_code is None:
        return {
            "url": url,
            "status": "unverifiable",
            "http_code": None,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": "Could not reach server (timeout or connection error)",
        }

    if 200 <= status_code < 400:
        return {
            "url": url,
            "status": "valid",
            "http_code": status_code,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": "URL is reachable",
        }

    if status_code == 403 and platform in SOCIAL_403_PLATFORMS:
        return {
            "url": url,
            "status": "unverifiable",
            "http_code": 403,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": "Platform blocks automated requests (403); URL pattern matches",
        }

    if status_code in (404, 410):
        return {
            "url": url,
            "status": "invalid",
            "http_code": status_code,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": "Page not found",
        }

    if status_code == 403:
        # Non-social 403 — suspicious but not provably invalid
        return {
            "url": url,
            "status": "unverifiable",
            "http_code": 403,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": "Access forbidden (403)",
        }

    if status_code >= 500:
        return {
            "url": url,
            "status": "unverifiable",
            "http_code": status_code,
            "redirected_to": final_url,
            "pattern_ok": True,
            "reason": f"Server error ({status_code})",
        }

    # Catch-all for other status codes (e.g. 451, 429)
    return {
        "url": url,
        "status": "unverifiable",
        "http_code": status_code,
        "redirected_to": final_url,
        "pattern_ok": True,
        "reason": f"Unexpected status code ({status_code})",
    }


async def validate_urls_batch(urls: list[dict]) -> list[dict]:
    """Validate multiple URLs concurrently.

    Args:
        urls: List of dicts, each with "url" and optionally "platform" keys.

    Returns:
        List of validation result dicts from validate_url.
    """
    tasks = [
        validate_url(u.get("url", ""), u.get("platform", ""))
        for u in urls
    ]
    return list(await asyncio.gather(*tasks))
