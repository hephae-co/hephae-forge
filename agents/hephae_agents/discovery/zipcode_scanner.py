"""Zip code business scanner — discovers businesses via Google Search + OSM + Municipal Hub crawling."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata

import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.firestore.businesses import get_businesses_in_zipcode, save_business
from hephae_db.schemas import ZipcodeScannerOutput
from hephae_common.model_fallback import fallback_on_error
from hephae_integrations.osm_client import discover_businesses as osm_discover
from hephae_api.types import DiscoveredBusiness

logger = logging.getLogger(__name__)

ZipcodeScannerAgent = LlmAgent(
    name="ZipcodeScanner",
    model=AgentModels.PRIMARY_MODEL,
    instruction="""You are a Local Business Discovery Agent. Your goal is to find AS MANY real, independently owned businesses as possible in the provided zip code. Aim for 30-50+ businesses.

Use Google Search extensively — make MULTIPLE searches to maximize coverage:
- "[zip code] local restaurants"
- "[zip code] business directory"
- "chamber of commerce [city name] members"
- Yelp, Google Maps, TripAdvisor listings for this area
- Local business associations and merchant directories
- "[city name] [category] independently owned"
- Search for businesses on EACH major street in the area

Do multiple rounds of searching to find businesses you may have missed.

IMPORTANT — EXCLUSION RULES: Do NOT include:
- National or regional chains, franchises, or corporate-owned locations
  (e.g., McDonald's, Burger King, Starbucks, Dunkin', Subway, Chipotle, Pizza Hut, Domino's,
  Taco Bell, KFC, Panera, Chick-fil-A, Wendy's, etc.)
- Banks or financial institutions (Chase, Wells Fargo, Bank of America, etc.)
- National retail chains (Walmart, Target, CVS, Walgreens, Home Depot, etc.)
- National gym/fitness chains (Planet Fitness, Anytime Fitness, etc.)
- Any business that is clearly a franchise or corporate-owned location

ONLY include independently owned local businesses.

Return ONLY a valid JSON object with a 'businesses' array. Each business must contain:
- 'name': the business name
- 'address': full street address including city and zip
- 'website': business website URL if found (or empty string)
- 'category': business category like "restaurant", "cafe", "salon", "auto repair", etc. (or empty string)

Example:
{
  "businesses": [
    { "name": "Pizza Planet", "address": "123 Rocket Way, Nutley, NJ 07110", "website": "https://pizzaplanet.com", "category": "restaurant" },
    { "name": "Main Street Cafe", "address": "456 Main St, Nutley, NJ 07110", "website": "", "category": "cafe" }
  ]
}""",
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)


def _generate_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _normalize_name(name: str) -> str:
    """Normalize a business name for deduplication comparison."""
    # Lowercase, strip accents, remove punctuation
    name = name.lower().strip()
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


async def _resolve_city_state(zip_code: str) -> tuple[str, str] | None:
    """Resolve city and state from a zip code via Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "postalcode": zip_code,
                    "country": "US",
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "hephae-admin/1.0 (business-discovery)"},
            )
        if resp.status_code != 200 or not resp.json():
            return None
        addr = resp.json()[0].get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village") or ""
        state = addr.get("state", "")
        if city:
            return city, state
    except Exception as e:
        logger.warning(f"[Scanner] Nominatim city/state lookup failed for {zip_code}: {e}")
    return None


async def _run_hub_discovery(zip_code: str, category: str | None = None) -> list[dict]:
    """Find municipal hub / chamber of commerce directory, crawl it, and extract businesses."""
    from hephae_agents.discovery.municipal_hubs import find_municipal_hub
    from hephae_agents.discovery.directory_parser import parse_directory_content
    from hephae_agents.shared_tools.crawl4ai import crawl_for_content

    location = await _resolve_city_state(zip_code)
    if not location:
        logger.info(f"[Scanner] Could not resolve city/state for {zip_code}, skipping hub discovery")
        return []

    city, state = location
    logger.info(f"[Scanner] Hub discovery: looking for directory in {city}, {state}...")

    hub_url = await find_municipal_hub(city, state)
    if not hub_url:
        logger.info(f"[Scanner] No municipal hub found for {city}, {state}")
        return []

    logger.info(f"[Scanner] Found hub: {hub_url}, crawling...")
    crawl_result = await crawl_for_content(hub_url)
    content = crawl_result.get("markdown") or crawl_result.get("text", "")
    if not content:
        logger.warning(f"[Scanner] Hub crawl returned no content for {hub_url}")
        return []

    businesses = await parse_directory_content(content, category=category)
    logger.info(f"[Scanner] Hub discovery found {len(businesses)} businesses from {hub_url}")
    return businesses


async def scan_zipcode(zip_code: str, category: str | None = None, force: bool = False) -> list[DiscoveredBusiness]:
    """Discover businesses in a zip code using 3 sources: Google Search + OSM + Municipal Hub.

    If category is provided (e.g. 'Bakeries'), discovery is much more targeted.
    Runs all three sources in parallel, merges and deduplicates results.
    """
    logger.info(f"[Scanner] Searching for {category or 'all'} businesses in {zip_code} (force={force})...")

    # 1. Check Firestore cache (skip if force=True or if searching specific category)
    if not force and not category:
        existing = await get_businesses_in_zipcode(zip_code, limit=30)
        if existing:
            logger.info(f"[Scanner] Found {len(existing)} cached businesses in {zip_code}.")
            return [
                DiscoveredBusiness(
                    name=b.get("name", ""), address=b.get("address", ""),
                    category=b.get("category", ""), website=b.get("website", ""),
                    docId=b["docId"],
                )
                for b in existing
            ]

    # 2. Run all three discovery sources in parallel
    logger.info(f"[Scanner] Running ADK + OSM + Hub for {zip_code} ({category or 'general'})...")
    osm_task = osm_discover(zip_code, category=category)
    adk_task = _run_adk_discovery(zip_code, category=category)
    hub_task = _run_hub_discovery(zip_code, category=category)
    osm_results, adk_results, hub_results = await asyncio.gather(
        osm_task, adk_task, hub_task, return_exceptions=True,
    )

    # Handle exceptions from any source gracefully
    if isinstance(osm_results, BaseException):
        logger.error(f"[Scanner] OSM discovery failed: {osm_results}")
        osm_results = []
    if isinstance(adk_results, BaseException):
        logger.error(f"[Scanner] ADK discovery failed: {adk_results}")
        adk_results = []
    if isinstance(hub_results, BaseException):
        logger.error(f"[Scanner] Hub discovery failed: {hub_results}")
        hub_results = []

    # 3. Merge and deduplicate (priority: Hub > ADK > OSM)
    seen: dict[str, DiscoveredBusiness] = {}

    # Hub results first (highest trust — official directories)
    for biz in hub_results:
        name_key = _normalize_name(biz.get("name", ""))
        if not name_key:
            continue
        slug = _generate_slug(biz["name"])
        seen[name_key] = DiscoveredBusiness(
            name=biz["name"],
            address=biz.get("address", ""),
            category=biz.get("category", ""),
            website=biz.get("website", ""),
            docId=slug,
        )

    # ADK results (Google Search grounding)
    for biz in adk_results:
        name_key = _normalize_name(biz["name"])
        if not name_key or name_key in seen:
            continue
        slug = _generate_slug(biz["name"])
        seen[name_key] = DiscoveredBusiness(
            name=biz["name"],
            address=biz.get("address", ""),
            category=biz.get("category", ""),
            website=biz.get("website", ""),
            docId=slug,
        )

    # OSM results fill remaining gaps
    for osm_biz in osm_results:
        name_key = _normalize_name(osm_biz.name)
        if not name_key or name_key in seen:
            continue
        slug = _generate_slug(osm_biz.name)
        address = osm_biz.address or ""
        biz_category = getattr(osm_biz, "category", "") or ""
        seen[name_key] = DiscoveredBusiness(
            name=osm_biz.name,
            address=address,
            category=biz_category,
            docId=slug,
        )

    results = list(seen.values())
    logger.info(
        f"[Scanner] Merged: {len(hub_results)} Hub + {len(adk_results)} ADK + {len(osm_results)} OSM → {len(results)} unique"
    )

    # 4. Persist each business to Firestore
    for biz in results:
        await save_business(biz.docId, {
            "name": biz.name,
            "address": biz.address,
            "category": biz.category,
            "website": biz.website,
            "zipCode": zip_code,
            "discoveryStatus": "scanned",
        })

    return results


async def _run_adk_discovery(zip_code: str, category: str | None = None) -> list[dict]:
    """Run the ADK agent with Google Search grounding to discover businesses."""
    if category:
        target = category.lower().rstrip("s")  # "Bakeries" → "bakery"
        query = (
            f"Find independently owned {category.lower()} currently operating in zip code {zip_code}. "
            f"Search for '{target} near {zip_code}', '{target} in {zip_code}', "
            f"local {target} directories, Yelp and Google Maps listings. "
            f"Only include local, independently owned {category.lower()}. "
            f"Exclude all chains, franchises, and national brands."
        )
    else:
        query = (
            f"Find real local businesses currently operating in zip code {zip_code}. "
            f"Search for local business directories, chamber of commerce member lists for {zip_code}. "
            f"Focus on independently owned local businesses only. Exclude all chains, franchises, banks, and national retailers."
        )
    
    try:
        # Note: google_search tool cannot be combined with response_schema (function calling),
        # so we parse the JSON from text output instead.
        result = await run_agent_to_json(
            ZipcodeScannerAgent,
            query,
            app_name="HephaeAdmin",
        )
        if result:
            raw_businesses = result.get("businesses", []) if isinstance(result, dict) else []
            businesses = [
                {
                    "name": b.get("name", ""),
                    "address": b.get("address", ""),
                    "website": b.get("website", ""),
                    "category": b.get("category") or category,
                }
                for b in raw_businesses
                if b.get("name")
            ]
            return businesses
    except Exception as e:
        logger.error(f"[Scanner] ADK agent failed: {e}")
    return []
