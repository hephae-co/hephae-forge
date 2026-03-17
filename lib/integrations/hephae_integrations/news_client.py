"""Local news client — multiple RSS sources with fallback.

Primary: Google News RSS
Fallback: Bing News RSS (when Google returns 503)

Used by the Weekly Pulse pipeline to provide local news context.
"""

from __future__ import annotations

import logging
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
BING_NEWS_RSS_URL = "https://www.bing.com/news/search"

# Rotate user agents to reduce 503 from Google
_USER_AGENTS = [
    "Mozilla/5.0 (compatible; Hephae/1.0; +https://hephae.co)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
]


def _clean_html(text: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_items(xml_text: str, max_items: int = 10) -> list[dict[str, Any]]:
    """Parse RSS XML into a list of news item dicts."""
    items: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("[NewsClient] Failed to parse RSS XML")
        return items

    channel = root.find("channel")
    if channel is None:
        return items

    for item_el in channel.findall("item"):
        if len(items) >= max_items:
            break

        title_el = item_el.find("title")
        link_el = item_el.find("link")
        pub_date_el = item_el.find("pubDate")
        desc_el = item_el.find("description")
        source_el = item_el.find("source")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title:
            continue

        pub_date = ""
        if pub_date_el is not None and pub_date_el.text:
            try:
                dt = parsedate_to_datetime(pub_date_el.text)
                pub_date = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pub_date = pub_date_el.text.strip()

        items.append({
            "headline": title,
            "url": link_el.text.strip() if link_el is not None and link_el.text else "",
            "publishedDate": pub_date,
            "summary": _clean_html(desc_el.text) if desc_el is not None and desc_el.text else "",
            "source": source_el.text.strip() if source_el is not None and source_el.text else "",
        })

    return items


async def _fetch_google_news(
    client: httpx.AsyncClient, query: str, max_items: int,
) -> list[dict[str, Any]]:
    """Try Google News RSS."""
    encoded = quote(query)
    url = f"{GOOGLE_NEWS_RSS_URL}?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            return _parse_rss_items(response.text, max_items=max_items)
        logger.warning(f"[NewsClient] Google RSS returned {response.status_code} for: {query}")
    except Exception as e:
        logger.warning(f"[NewsClient] Google RSS failed for: {query} — {e}")
    return []


async def _fetch_bing_news(
    client: httpx.AsyncClient, query: str, max_items: int,
) -> list[dict[str, Any]]:
    """Fallback: Bing News RSS."""
    encoded = quote(query)
    url = f"{BING_NEWS_RSS_URL}?q={encoded}&format=rss&count={max_items}"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            items = _parse_rss_items(response.text, max_items=max_items)
            if items:
                logger.info(f"[NewsClient] Bing fallback returned {len(items)} articles for: {query}")
            return items
        logger.warning(f"[NewsClient] Bing RSS returned {response.status_code} for: {query}")
    except Exception as e:
        logger.warning(f"[NewsClient] Bing RSS failed for: {query} — {e}")
    return []


async def query_local_news(
    location: str,
    business_type: str = "",
    max_items: int = 10,
) -> dict[str, Any]:
    """Fetch recent local news for a location via RSS feeds.

    Tries Google News first, falls back to Bing News if Google returns 503.
    Uses multiple query variations to maximize coverage.
    """
    empty: dict[str, Any] = {"articles": [], "location": location, "fetchedAt": ""}

    # Build diverse queries for better coverage
    # Strip "city" suffix for cleaner search (e.g. "Clifton city" → "Clifton")
    clean_location = re.sub(r"\s+(city|town|village|borough|CDP)\b", "", location, flags=re.IGNORECASE).strip()

    queries = [
        f"{clean_location} local news",
        f"{clean_location} business development",
    ]
    if business_type:
        queries.append(f"{clean_location} {business_type}")

    all_articles: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    google_failed = False

    try:
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for query in queries:
                # Try Google first
                items = await _fetch_google_news(client, query, max_items)
                if not items:
                    google_failed = True
                    # Fallback to Bing
                    items = await _fetch_bing_news(client, query, max_items)

                for item in items:
                    title_key = item["headline"].lower().strip()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_articles.append(item)

        # Sort by date (most recent first), limit to max_items
        all_articles.sort(key=lambda a: a.get("publishedDate", ""), reverse=True)
        all_articles = all_articles[:max_items]

        source_note = " (via Bing fallback)" if google_failed and all_articles else ""
        logger.info(f"[NewsClient] Fetched {len(all_articles)} articles for {clean_location}{source_note}")

        return {
            "articles": all_articles,
            "location": clean_location,
            "fetchedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[NewsClient] Failed to fetch news for {location}: {e}")
        return empty
