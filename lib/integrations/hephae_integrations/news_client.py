"""Google News RSS client for local news aggregation.

Fetches recent news headlines for a location via Google News RSS feeds.
Used by the Weekly Pulse pipeline to provide local news context.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


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


async def query_local_news(
    location: str,
    business_type: str = "",
    max_items: int = 10,
) -> dict[str, Any]:
    """Fetch recent local news for a location via Google News RSS.

    Args:
        location: City/town name or "City, State" string.
        business_type: Optional business type to include in search.
        max_items: Maximum number of news items to return.

    Returns:
        Dict with "articles" list and metadata.
    """
    empty: dict[str, Any] = {"articles": [], "location": location, "fetchedAt": ""}

    # Build search queries — one general local news, one business-specific
    queries = [f"{location} local news"]
    if business_type:
        queries.append(f"{location} {business_type} business")

    all_articles: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for query in queries:
                encoded_query = quote(query)
                url = f"{GOOGLE_NEWS_RSS_URL}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"[NewsClient] RSS returned {response.status_code} for query: {query}")
                    continue

                items = _parse_rss_items(response.text, max_items=max_items)
                for item in items:
                    # Deduplicate by title
                    title_key = item["headline"].lower().strip()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        all_articles.append(item)

        # Sort by date (most recent first), limit to max_items
        all_articles.sort(key=lambda a: a.get("publishedDate", ""), reverse=True)
        all_articles = all_articles[:max_items]

        logger.info(f"[NewsClient] Fetched {len(all_articles)} articles for {location}")

        return {
            "articles": all_articles,
            "location": location,
            "fetchedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[NewsClient] Failed to fetch news for {location}: {e}")
        return empty
