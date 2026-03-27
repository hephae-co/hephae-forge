"""Industry Research Reference Harvester.

Weekly crawl that finds authoritative external research on topics relevant
to Hephae's work (restaurant margins, food costs, commodity prices, small
business profitability, restaurant tech, labor).

TWO-TRACK ARCHITECTURE:

Track A — Google News RSS (fast, no page fetch needed):
  RSS items already contain: title, source name, source domain URL, pub date.
  Gemini classifies title + source → topics, inferred stats, relevance score.
  Stores Google News link as the reference URL (still clickable).

Track B — Authority site direct crawl (deeper, content-based):
  5-10 known-good domains (ers.usda.gov, restaurant.org, bls.gov news releases,
  etc.) are fetched directly — their HTML is readable without JS.
  Gemini extracts key stats and summary from actual page text.

Together these produce 20-50 well-structured references per week that blogs,
outreach, and pulse synthesis can cite as real external evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Topic clusters and search queries ─────────────────────────────────────────

TOPIC_CLUSTERS: dict[str, list[str]] = {
    "restaurant_food_cost": [
        "restaurant food cost percentage 2025 2026 research",
        "restaurant margins profitability study NRA",
        "food cost benchmarks casual dining industry 2026",
        "restaurant operating costs inflation 2026",
    ],
    "commodity_inflation": [
        "food commodity price inflation restaurant 2026",
        "BLS food prices report restaurant impact 2026",
        "eggs coffee beef restaurant supply chain inflation 2026",
        "food input costs small business 2026",
    ],
    "restaurant_industry_trends": [
        "restaurant industry outlook 2026 report",
        "restaurant closures openings statistics 2026",
        "National Restaurant Association report 2026",
        "restaurant consumer spending trends 2026",
        "independent restaurant survival study",
    ],
    "small_business_margins": [
        "small business profitability margins 2025 2026 study",
        "small business food service financial benchmarks",
        "SBA restaurant economics 2026",
        "independent restaurant chain financial performance comparison",
    ],
    "menu_pricing_strategy": [
        "restaurant menu pricing strategy research 2026",
        "menu engineering profitability study",
        "restaurant price increase consumer acceptance 2026",
    ],
    "restaurant_technology": [
        "restaurant technology impact revenue margins 2026",
        "restaurant delivery platform commission fees study",
        "restaurant POS analytics small business ROI",
    ],
    "labor_costs_restaurants": [
        "restaurant labor cost percentage 2026 study",
        "minimum wage restaurant impact research 2026",
        "restaurant staffing costs profitability",
    ],
}

# ── Authority domains: direct crawl targets ────────────────────────────────────
# Pages that serve real HTML content (no JS rendering) and publish regular research.

AUTHORITY_CRAWL_TARGETS: list[dict[str, str]] = [
    # USDA ERS — serves real HTML
    {
        "url": "https://www.ers.usda.gov/topics/food-markets-prices",
        "name": "USDA Economic Research Service",
        "type": "government",
        "topic_hint": "commodity_inflation",
    },
    {
        "url": "https://www.ers.usda.gov/data-products/food-price-outlook/",
        "name": "USDA Economic Research Service",
        "type": "government",
        "topic_hint": "restaurant_food_cost",
    },
    # BLS — txt format bypasses HTML bot blocks
    {
        "url": "https://www.bls.gov/news.release/cpi.t01.htm",
        "name": "Bureau of Labor Statistics",
        "type": "government",
        "topic_hint": "commodity_inflation",
    },
    # National Restaurant Association — research stats page (not report page)
    {
        "url": "https://restaurant.org/research-and-media/research/industry-statistics/",
        "name": "National Restaurant Association",
        "type": "industry_assoc",
        "topic_hint": "restaurant_industry_trends",
    },
    # Toast restaurant industry data
    {
        "url": "https://pos.toasttab.com/resources/restaurant-success-report",
        "name": "Toast",
        "type": "industry_data",
        "topic_hint": "small_business_margins",
    },
    # Restaurant Business — financing/operations section
    {
        "url": "https://www.restaurantbusinessonline.com/operations",
        "name": "Restaurant Business",
        "type": "trade_press",
        "topic_hint": "restaurant_food_cost",
    },
    # QSR Magazine
    {
        "url": "https://www.qsrmagazine.com/content/qsr-50",
        "name": "QSR Magazine",
        "type": "trade_press",
        "topic_hint": "restaurant_industry_trends",
    },
    # Nation's Restaurant News — news feed
    {
        "url": "https://www.nrn.com/",
        "name": "Nation's Restaurant News",
        "type": "trade_press",
        "topic_hint": "restaurant_industry_trends",
    },
    # Food on Demand News — delivery/tech
    {
        "url": "https://foodondemandnews.com/",
        "name": "Food On Demand News",
        "type": "trade_press",
        "topic_hint": "restaurant_technology",
    },
    # Technomic insights blog
    {
        "url": "https://www.technomic.com/insights",
        "name": "Technomic",
        "type": "market_research",
        "topic_hint": "restaurant_industry_trends",
    },
]

# ── Known-authority source domains (for RSS scoring) ──────────────────────────

AUTHORITY_SOURCES: dict[str, tuple[str, str]] = {
    "ers.usda.gov": ("USDA Economic Research Service", "government"),
    "bls.gov": ("Bureau of Labor Statistics", "government"),
    "census.gov": ("U.S. Census Bureau", "government"),
    "sba.gov": ("Small Business Administration", "government"),
    "fda.gov": ("FDA", "government"),
    "restaurant.org": ("National Restaurant Association", "industry_assoc"),
    "deloitte.com": ("Deloitte", "consulting"),
    "mckinsey.com": ("McKinsey & Company", "consulting"),
    "pwc.com": ("PwC", "consulting"),
    "kpmg.com": ("KPMG", "consulting"),
    "technomic.com": ("Technomic", "market_research"),
    "datassential.com": ("Datassential", "market_research"),
    "toasttab.com": ("Toast", "industry_data"),
    "pymnts.com": ("PYMNTS", "fintech_news"),
    "qsrmagazine.com": ("QSR Magazine", "trade_press"),
    "restaurantbusinessonline.com": ("Restaurant Business", "trade_press"),
    "nationsrestaurantnews.com": ("Nation's Restaurant News", "trade_press"),
    "nrn.com": ("Nation's Restaurant News", "trade_press"),
    "foodbusinessnews.net": ("Food Business News", "trade_press"),
    "modernrestaurantmanagement.com": ("Modern Restaurant Management", "trade_press"),
    "squareup.com": ("Square", "industry_data"),
    "forbes.com": ("Forbes", "business_press"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Utilities ──────────────────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _extract_text(html: str, max_chars: int = 5000) -> str:
    """Strip HTML → clean text."""
    text = re.sub(
        r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>",
        " ", html, flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


async def _get(client: httpx.AsyncClient, url: str, timeout: float = 12.0) -> str | None:
    try:
        resp = await client.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        logger.debug(f"[Harvester] {resp.status_code} for {url}")
    except Exception as e:
        logger.debug(f"[Harvester] GET failed {url}: {e}")
    return None


# ── Track A: Google News RSS ───────────────────────────────────────────────────

async def _fetch_rss_items(
    client: httpx.AsyncClient,
    query: str,
    topic_hint: str,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    """Fetch Google News RSS and return structured items (no page fetching)."""
    encoded = re.sub(r"\s+", "+", query.strip())
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    xml_text = await _get(client, url)
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
        items = []
        for item in root.findall(".//item")[:max_results]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            source_el = item.find("source")

            if title_el is None or not title_el.text:
                continue

            # Source name and domain from RSS source element
            source_name = source_el.text.strip() if source_el is not None else "Unknown"
            source_url = source_el.get("url", "") if source_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""

            # Determine source type and authority boost
            source_type = "news"
            authority_boost = 0.0
            for domain, (auth_name, auth_type) in AUTHORITY_SOURCES.items():
                if domain in source_url:
                    source_name = auth_name
                    source_type = auth_type
                    authority_boost = 0.25
                    break

            # Published date — parse to YYYY-MM
            pub_date = None
            if pub_el is not None and pub_el.text:
                try:
                    dt = datetime.strptime(pub_el.text[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    pub_date = dt.strftime("%Y-%m")
                except ValueError:
                    pub_date = pub_el.text[:10] if pub_el.text else None

            items.append({
                "title": title_el.text.strip(),
                "url": link,
                "source": source_name,
                "source_url": source_url,
                "source_type": source_type,
                "published_date": pub_date,
                "topic_hint": topic_hint,
                "authority_boost": authority_boost,
                "track": "rss",
            })
        return items
    except ET.ParseError:
        return []


# ── Track A: Gemini batch title classification ─────────────────────────────────

_CLASSIFY_PROMPT = """\
You are a research classification AI for a restaurant intelligence platform.

Classify each of these article titles+sources. Return a JSON array (one object per item, same order).

For each:
{{
  "topics": ["up to 3 tags from: restaurant_food_cost | commodity_inflation | restaurant_industry_trends | small_business_margins | menu_pricing_strategy | restaurant_technology | labor_costs_restaurants | irrelevant"],
  "key_stats": ["up to 2 specific numbers or findings you can infer from the TITLE ALONE — e.g. '$162B food waste' or '3.5% menu price increase'. Empty array if none visible."],
  "summary": "one sentence factual summary inferred from title",
  "relevance_score": 0.0-1.0 (how useful for restaurant margin/food cost intelligence — 0 if irrelevant)
}}

Articles to classify:
{articles}

Return ONLY the JSON array."""


async def _classify_titles_batch(
    client: httpx.AsyncClient,
    gemini_key: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Batch-classify RSS item titles using Gemini (no page fetch needed)."""
    if not items:
        return []

    # Build article list for prompt
    article_lines = "\n".join(
        f'{i+1}. [{item["source"]}] {item["title"]}'
        for i, item in enumerate(items)
    )
    prompt = _CLASSIFY_PROMPT.format(articles=article_lines)

    try:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 8192},
            },
            timeout=30.0,
        )
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        classifications = json.loads(raw)
        return classifications if isinstance(classifications, list) else []
    except Exception as e:
        logger.warning(f"[Harvester] Batch classification failed: {e}")
        return []


# ── Track B: Authority site direct crawl ──────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a research analyst extracting metadata from a page for a restaurant intelligence platform.

Given the URL, source name, and page text, extract structured metadata as JSON.
Only include fields you are confident about from the text. Do not guess.

{{
  "title": "main page/report title",
  "published_date": "YYYY-MM or YYYY if visible, else null",
  "topics": ["up to 4 tags: restaurant_food_cost | commodity_inflation | restaurant_industry_trends | small_business_margins | menu_pricing_strategy | restaurant_technology | labor_costs_restaurants"],
  "key_stats": ["up to 4 specific quantitative claims from the text — exact numbers/percentages"],
  "summary": "1-2 sentence factual summary of main findings",
  "relevance_score": 0.0-1.0
}}

If the page is a login wall, error page, or mostly navigation, return {{"relevance_score": 0}}.
Do NOT invent statistics.

Source: {source}
URL: {url}
Page text:
{text}

Output only the JSON object."""


async def _crawl_authority_target(
    client: httpx.AsyncClient,
    gemini_key: str,
    target: dict[str, str],
) -> dict[str, Any] | None:
    """Fetch an authority page and extract structured metadata."""
    html = await _get(client, target["url"])
    if not html:
        return None

    text = _extract_text(html, max_chars=5000)
    if len(text) < 200:
        logger.debug(f"[Harvester] Authority page too short: {target['url']}")
        return None

    prompt = _EXTRACT_PROMPT.format(
        source=target["name"],
        url=target["url"],
        text=text,
    )

    try:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
            },
            timeout=20.0,
        )
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        meta = json.loads(raw)
    except Exception as e:
        logger.debug(f"[Harvester] Authority extraction failed {target['url']}: {e}")
        return None

    score = float(meta.get("relevance_score", 0))
    if score < 0.3:
        return None

    return {
        "id": _url_hash(target["url"]),
        "url": target["url"],
        "title": meta.get("title") or target["name"] + " — Research",
        "source": target["name"],
        "source_type": target["type"],
        "published_date": meta.get("published_date"),
        "topics": meta.get("topics") or [target.get("topic_hint", "")],
        "key_stats": [s for s in (meta.get("key_stats") or []) if s],
        "summary": meta.get("summary", ""),
        "relevance_score": round(min(score, 1.0), 3),
        "track": "authority_crawl",
    }


# ── Main harvester ─────────────────────────────────────────────────────────────

async def harvest_references(
    topics: list[str] | None = None,
    week_of: str | None = None,
    existing_url_hashes: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Harvest research references across both tracks.

    Track A: Google News RSS → title-based Gemini classification (fast, ~40 items).
    Track B: Authority site direct crawl → content-based extraction (~10 items).
    """
    if week_of is None:
        week_of = datetime.utcnow().strftime("%Y-W%W")
    if topics is None:
        topics = list(TOPIC_CLUSTERS.keys())
    if existing_url_hashes is None:
        existing_url_hashes = set()

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not set")

    references: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:

        # ── Track A: Google News RSS ────────────────────────────────────────────
        logger.info(f"[Harvester] Track A: Google News RSS ({len(topics)} topic clusters)")

        rss_tasks = []
        for topic_key in topics:
            for query in TOPIC_CLUSTERS.get(topic_key, [])[:3]:  # cap at 3 queries/topic
                rss_tasks.append(_fetch_rss_items(client, query, topic_key))

        all_rss_items: list[dict[str, Any]] = []
        rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
        for r in rss_results:
            if isinstance(r, list):
                all_rss_items.extend(r)

        logger.info(f"[Harvester] {len(all_rss_items)} raw RSS items")

        # Deduplicate by URL hash
        seen_hashes: set[str] = set(existing_url_hashes)
        unique_rss: list[dict[str, Any]] = []
        for item in all_rss_items:
            h = _url_hash(item["url"])
            if h not in seen_hashes and item["url"]:
                seen_hashes.add(h)
                item["id"] = h
                unique_rss.append(item)

        # Sort: authority sources first
        unique_rss.sort(key=lambda x: -x.get("authority_boost", 0))

        # Cap at 60 for batch classification
        unique_rss = unique_rss[:60]
        logger.info(f"[Harvester] {len(unique_rss)} unique RSS items to classify")

        # Batch classify in chunks of 10 (smaller = less JSON truncation risk)
        CHUNK = 10
        for i in range(0, len(unique_rss), CHUNK):
            chunk = unique_rss[i: i + CHUNK]
            classifications = await _classify_titles_batch(client, gemini_key, chunk)
            for j, cls in enumerate(classifications):
                if j >= len(chunk):
                    break
                item = chunk[j]
                score = float(cls.get("relevance_score", 0)) + item.get("authority_boost", 0)
                if score < 0.35:
                    continue
                topics_found = [t for t in cls.get("topics", []) if t != "irrelevant"]
                if not topics_found:
                    continue
                references.append({
                    "id": item["id"],
                    "url": item["url"],
                    "title": item["title"],
                    "source": item["source"],
                    "source_type": item["source_type"],
                    "published_date": item.get("published_date"),
                    "topics": topics_found,
                    "key_stats": [s for s in cls.get("key_stats", []) if s],
                    "summary": cls.get("summary", ""),
                    "relevance_score": round(min(score, 1.0), 3),
                    "week_of": week_of,
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
                    "track": "rss",
                })

        logger.info(f"[Harvester] Track A complete: {len(references)} references (score ≥ 0.35)")

        # ── Track B: Authority site direct crawl ────────────────────────────────
        logger.info(f"[Harvester] Track B: Authority crawl ({len(AUTHORITY_CRAWL_TARGETS)} targets)")

        sem = asyncio.Semaphore(3)

        async def crawl_one(target: dict[str, str]) -> dict[str, Any] | None:
            h = _url_hash(target["url"])
            if h in seen_hashes:
                return None
            async with sem:
                result = await _crawl_authority_target(client, gemini_key, target)
                if result:
                    result["week_of"] = week_of
                    result["fetched_at"] = datetime.utcnow().isoformat() + "Z"
                    seen_hashes.add(h)
                return result

        crawl_results = await asyncio.gather(
            *[crawl_one(t) for t in AUTHORITY_CRAWL_TARGETS],
            return_exceptions=True,
        )
        for r in crawl_results:
            if isinstance(r, dict):
                references.append(r)

        authority_count = sum(1 for r in crawl_results if isinstance(r, dict))
        logger.info(f"[Harvester] Track B complete: {authority_count} authority references")

    references.sort(key=lambda x: -x["relevance_score"])
    logger.info(f"[Harvester] Total: {len(references)} references ready to save")
    return references


async def run_weekly_harvest(week_of: str | None = None) -> dict[str, Any]:
    """Top-level entry point called by the cron handler."""
    from hephae_db.firestore.research_references import (
        get_existing_url_hashes,
        save_references,
    )

    if week_of is None:
        week_of = datetime.utcnow().strftime("%Y-W%W")

    existing = await get_existing_url_hashes()
    logger.info(f"[Harvester] {len(existing)} existing references, skipping those")

    refs = await harvest_references(week_of=week_of, existing_url_hashes=existing)
    saved = await save_references(refs)

    topic_counts: dict[str, int] = {}
    for r in refs:
        for t in r.get("topics", []):
            topic_counts[t] = topic_counts.get(t, 0) + 1

    source_types: dict[str, int] = {}
    for r in refs:
        st = r.get("source_type", "unknown")
        source_types[st] = source_types.get(st, 0) + 1

    return {
        "week_of": week_of,
        "harvested": len(refs),
        "saved": saved,
        "by_topic": topic_counts,
        "by_source_type": source_types,
        "top_sources": list({r["source"] for r in refs[:20]}),
        "sample": [
            {
                "title": r["title"],
                "source": r["source"],
                "score": r["relevance_score"],
                "stats": r.get("key_stats", [])[:2],
            }
            for r in refs[:8]
        ],
    }
