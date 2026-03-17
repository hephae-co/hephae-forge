"""NJ Department of State legal notice portal scraper for business-relevant public notices."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = "Hephae/1.0 (contact@hephae.co)"

# Known NJ legal notice endpoints and search patterns
_NJ_LEGAL_NOTICES_URL = "https://www.nj.gov/state/dos-legal-notices.shtml"
_NJ_BUSINESS_SEARCH_URL = "https://www.njportal.com/DOR/BusinessNameSearch"

# Notice type classification patterns
_NOTICE_PATTERNS: dict[str, list[str]] = {
    "liquor_license": [
        r"liquor\s+license", r"alcohol\s+beverage", r"plenary\s+retail",
        r"bar\s+license", r"consumption\s+license",
    ],
    "zoning_variance": [
        r"zoning\s+(?:variance|change|amendment)", r"land\s+use",
        r"planning\s+board", r"zoning\s+board",
    ],
    "public_hearing": [
        r"public\s+hearing", r"public\s+notice", r"municipal\s+hearing",
        r"council\s+meeting",
    ],
    "business_filing": [
        r"business\s+(?:filing|registration|certificate)",
        r"trade\s+name", r"new\s+business", r"certificate\s+of\s+formation",
        r"llc\s+formation",
    ],
}


def _classify_notice(text: str) -> str:
    """Classify a notice into a category based on text patterns."""
    text_lower = text.lower()
    for notice_type, patterns in _NOTICE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return notice_type
    return "public_hearing"


def _extract_notices_from_html(html: str, city: str) -> list[dict[str, Any]]:
    """Extract notice-like items from raw HTML, filtering by city name."""
    notices: list[dict[str, Any]] = []
    city_lower = city.lower()

    # Look for text blocks that mention the city and contain notice keywords
    # Split on common HTML block delimiters
    blocks = re.split(r"<(?:div|p|li|tr|article|section)[^>]*>", html, flags=re.IGNORECASE)

    for block in blocks:
        # Strip HTML tags for text matching
        text = re.sub(r"<[^>]+>", " ", block).strip()
        text = re.sub(r"\s+", " ", text)

        if not text or len(text) < 20:
            continue

        if city_lower not in text.lower():
            continue

        # Check if it looks like a notice
        notice_keywords = [
            "notice", "hearing", "license", "zoning", "variance",
            "filing", "ordinance", "resolution", "permit",
        ]
        if not any(kw in text.lower() for kw in notice_keywords):
            continue

        # Extract a date if present
        date_match = re.search(
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})", text
        )
        date_str = date_match.group(1) if date_match else ""

        notice_type = _classify_notice(text)

        # Truncate description to a reasonable length
        description = text[:500] if len(text) > 500 else text

        notices.append({
            "type": notice_type,
            "description": description,
            "date": date_str,
            "sourceUrl": _NJ_LEGAL_NOTICES_URL,
        })

    return notices


def _build_search_urls(city: str, zip_code: str) -> list[dict[str, str]]:
    """Build URLs for manually checking NJ legal notice sources."""
    city_encoded = quote_plus(city)
    urls: list[dict[str, str]] = []

    urls.append({
        "source": "NJ DOS Legal Notices",
        "url": _NJ_LEGAL_NOTICES_URL,
        "description": "NJ Department of State official legal notice portal",
    })

    urls.append({
        "source": "NJ Business Name Search",
        "url": _NJ_BUSINESS_SEARCH_URL,
        "description": "Search for new business filings in NJ",
    })

    urls.append({
        "source": "NJ Open Public Records",
        "url": f"https://www.nj.gov/opra/",
        "description": "NJ Open Public Records Act portal",
    })

    # Municipal-level search (many NJ towns have their own legal notice pages)
    urls.append({
        "source": f"{city} Municipal Notices",
        "url": f"https://www.google.com/search?q={city_encoded}+NJ+%22legal+notice%22+OR+%22public+hearing%22+site%3A.gov",
        "description": f"Google search for {city}, NJ municipal legal notices",
    })

    if zip_code:
        urls.append({
            "source": "NJ.com Local News",
            "url": f"https://www.google.com/search?q={city_encoded}+NJ+{zip_code}+%22liquor+license%22+OR+%22zoning+variance%22+site%3Anj.com",
            "description": f"NJ.com local news search for {city} business notices",
        })

    return urls


def _generate_summary(
    notices: list[dict[str, Any]],
    new_filings: int,
    zoning_changes: int,
) -> str:
    """Generate a one-line summary of legal notice findings."""
    if not notices and not new_filings and not zoning_changes:
        return "No legal notices found for this area."

    parts: list[str] = []
    if notices:
        parts.append(f"{len(notices)} notice(s) found")
    if new_filings:
        parts.append(f"{new_filings} new business filing(s)")
    if zoning_changes:
        parts.append(f"{zoning_changes} zoning change(s)")
    return "; ".join(parts) + "."


async def query_legal_notices(
    city: str,
    state: str = "NJ",
    zip_code: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query NJ legal notice sources for business-relevant public notices.

    Attempts to scrape the NJ DOS legal notice portal and returns structured
    notice data. Gracefully degrades to returning search-ready URLs if scraping
    fails.

    Args:
        city: City name to search for notices in.
        state: State abbreviation (default "NJ").
        zip_code: Optional zip code for more specific results.
        cache_reader: Optional async fn(source, key, sub) -> dict | None
        cache_writer: Optional async fn(source, key, sub, data) -> None

    Returns:
        Dict with notices, newBusinessFilings, zoningChanges, summary, and sources.
    """
    empty: dict[str, Any] = {
        "notices": [],
        "newBusinessFilings": 0,
        "zoningChanges": 0,
        "summary": "No legal notices found for this area.",
        "sources": [],
    }

    if not city:
        return empty

    cache_key = f"{city.lower()}-{state.lower()}"
    if cache_reader:
        try:
            cached = await cache_reader("nj_legal", cache_key, zip_code)
            if cached:
                return cached
        except Exception:
            pass

    notices: list[dict[str, Any]] = []
    sources = _build_search_urls(city, zip_code)

    try:
        logger.info(f"[NJ-Legal] Fetching legal notices for {city}, {state}")

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Attempt to scrape the NJ DOS legal notices page
            try:
                resp = await client.get(
                    _NJ_LEGAL_NOTICES_URL,
                    headers={"User-Agent": _USER_AGENT},
                )
                if resp.status_code == 200:
                    extracted = _extract_notices_from_html(resp.text, city)
                    notices.extend(extracted)
                    logger.info(f"[NJ-Legal] Extracted {len(extracted)} notices from DOS portal")
                else:
                    logger.warning(f"[NJ-Legal] DOS portal returned {resp.status_code}")
            except Exception as e:
                logger.warning(f"[NJ-Legal] DOS portal scrape failed: {e}")

            # Attempt to check the NJ business search portal
            try:
                resp = await client.get(
                    _NJ_BUSINESS_SEARCH_URL,
                    headers={"User-Agent": _USER_AGENT},
                )
                if resp.status_code == 200:
                    extracted = _extract_notices_from_html(resp.text, city)
                    notices.extend(extracted)
            except Exception as e:
                logger.warning(f"[NJ-Legal] Business search scrape failed: {e}")

    except Exception as e:
        logger.error(f"[NJ-Legal] Legal notice query failed: {e}")
        # Gracefully degrade — still return sources for manual checking
        empty["sources"] = sources
        return empty

    # Count by type
    new_filings = sum(1 for n in notices if n["type"] == "business_filing")
    zoning_changes = sum(1 for n in notices if n["type"] == "zoning_variance")

    summary = _generate_summary(notices, new_filings, zoning_changes)

    logger.info(
        f"[NJ-Legal] {city}, {state}: {len(notices)} notices, "
        f"{new_filings} filings, {zoning_changes} zoning changes"
    )

    result: dict[str, Any] = {
        "notices": notices,
        "newBusinessFilings": new_filings,
        "zoningChanges": zoning_changes,
        "summary": summary,
        "sources": sources,
    }

    if cache_writer:
        try:
            await cache_writer("nj_legal", cache_key, zip_code, result)
        except Exception:
            pass

    return result
