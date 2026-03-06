"""Zip code business scanner — discovers businesses via Google Search grounding + OpenStreetMap."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from backend.config import AgentModels
from backend.lib.adk_helpers import run_agent_to_json
from backend.lib.db.businesses import get_businesses_in_zipcode, save_business
from backend.lib.model_fallback import fallback_on_error
from backend.lib.osm_client import discover_businesses as osm_discover
from backend.types import DiscoveredBusiness

logger = logging.getLogger(__name__)

ZipcodeScannerAgent = LlmAgent(
    name="ZipcodeScanner",
    model=AgentModels.PRIMARY_MODEL,
    instruction="""You are a Local Business Discovery Agent. Your goal is to find 15-20 real businesses operating in the provided zip code.

Use Google Search to find businesses by searching for:
- Local chamber of commerce business directories for this zip code
- Yelp listings and Google Maps results for this area
- Local business associations and merchant directories
- "businesses in [zip code]" and "restaurants near [zip code]"

Include a diverse mix: restaurants, cafes, retail shops, salons, auto repair, medical offices, pharmacies, gyms, etc.

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


async def scan_zipcode(zip_code: str, force: bool = False) -> list[DiscoveredBusiness]:
    """Discover businesses in a zip code using Google Search + OSM, then persist to Firestore.

    Runs both sources in parallel, merges and deduplicates results.
    """
    logger.info(f"[Scanner] Searching for businesses in {zip_code} (force={force})...")

    # 1. Check Firestore cache (skip if force=True)
    if not force:
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

    # 2. Run both discovery sources in parallel
    logger.info(f"[Scanner] Running Google Search agent + OSM for {zip_code}...")
    osm_task = osm_discover(zip_code)
    adk_task = _run_adk_discovery(zip_code)
    osm_results, adk_results = await asyncio.gather(osm_task, adk_task, return_exceptions=True)

    # Handle exceptions from either source gracefully
    if isinstance(osm_results, BaseException):
        logger.error(f"[Scanner] OSM discovery failed: {osm_results}")
        osm_results = []
    if isinstance(adk_results, BaseException):
        logger.error(f"[Scanner] ADK discovery failed: {adk_results}")
        adk_results = []

    # 3. Merge and deduplicate
    seen: dict[str, DiscoveredBusiness] = {}

    # ADK results first (Google Search grounding = higher quality)
    for biz in adk_results:
        name_key = _normalize_name(biz["name"])
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

    # OSM results fill gaps
    for osm_biz in osm_results:
        name_key = _normalize_name(osm_biz.name)
        if not name_key or name_key in seen:
            continue
        slug = _generate_slug(osm_biz.name)
        address = osm_biz.address or ""
        category = getattr(osm_biz, "category", "") or ""
        seen[name_key] = DiscoveredBusiness(
            name=osm_biz.name,
            address=address,
            category=category,
            docId=slug,
        )

    results = list(seen.values())
    logger.info(
        f"[Scanner] Merged: {len(adk_results)} ADK + {len(osm_results)} OSM → {len(results)} unique businesses"
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


async def _run_adk_discovery(zip_code: str) -> list[dict]:
    """Run the ADK agent with Google Search grounding to discover businesses."""
    try:
        data = await run_agent_to_json(
            ZipcodeScannerAgent,
            f"Find real businesses currently operating in zip code {zip_code}. "
            f"Search for local business directories, Yelp listings, and chamber of commerce for {zip_code}.",
            app_name="HephaeAdmin",
        )
        if data and isinstance(data, dict):
            businesses = data.get("businesses", [])
            return [b for b in businesses if b.get("name")]
    except Exception as e:
        logger.error(f"[Scanner] ADK agent failed: {e}")
    return []
