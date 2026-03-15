"""Discovery phase — finds businesses via scan_zipcode (Google Search + OSM)."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable

from hephae_agents.discovery.zipcode_scanner import scan_zipcode
from hephae_db.firestore.businesses import get_business
from hephae_api.types import BusinessWorkflowState, BusinessPhase

logger = logging.getLogger(__name__)


def generate_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", name.lower()).strip()
    slug = re.sub(r"\s+", "-", slug)
    return re.sub(r"-+", "-", slug)


def _dedup_key(name: str, address: str) -> str:
    norm_name = re.sub(r"[^a-z0-9]", "", name.lower())
    norm_addr = re.sub(r"[^a-z0-9]", "", address.lower())[:20]
    return f"{norm_name}::{norm_addr}"


async def run_discovery_phase(
    zip_code: str, business_type: str = "Restaurants"
) -> list[dict]:
    """Discover businesses in a single zip code via scan_zipcode.

    Uses the same code path as the Businesses tab — Google Search + OSM
    parallel discovery with dedup and Firestore persistence.
    """
    logger.info(f"[Workflow:Discovery] Discovering {business_type} in {zip_code}")
    results = await scan_zipcode(zip_code, category=business_type, force=True)

    return [
        {
            "slug": biz.docId or generate_slug(biz.name),
            "name": biz.name,
            "address": biz.address,
            "officialUrl": getattr(biz, "website", None),
            "sourceZipCode": zip_code,
            "businessType": business_type,
        }
        for biz in results
    ]


async def run_multi_zip_discovery_phase(
    zip_codes: list[str],
    business_type: str = "Restaurants",
    on_progress: Callable | None = None,
) -> list[dict]:
    """Discover businesses across multiple zip codes with deduplication."""
    logger.info(f"[Workflow:MultiZip] Scanning {len(zip_codes)} zip codes for {business_type}")

    all_businesses: list[dict] = []
    seen: set[str] = set()

    for i, zip_code in enumerate(zip_codes):
        if on_progress:
            on_progress({"zipCode": zip_code, "index": i, "total": len(zip_codes), "businessesFound": len(all_businesses)})

        discovered = await run_discovery_phase(zip_code, business_type)

        for biz in discovered:
            key = _dedup_key(biz["name"], biz["address"])
            if key not in seen:
                seen.add(key)
                all_businesses.append(biz)
            else:
                logger.info(f'[Workflow:MultiZip] Dedup: skipping "{biz["name"]}" from {zip_code}')

    logger.info(f"[Workflow:MultiZip] Total: {len(all_businesses)} unique businesses from {len(zip_codes)} zip codes")
    return all_businesses


async def _inherit_urls_from_firestore(discovered: list[dict]) -> list[dict]:
    """For businesses missing URLs, check if Firestore has one from a prior run."""
    missing = [b for b in discovered if not b.get("officialUrl")]
    if not missing:
        return discovered

    inherited = 0
    for biz in missing:
        try:
            existing = await get_business(biz["slug"])
            if existing and existing.get("officialUrl"):
                biz["officialUrl"] = existing["officialUrl"]
                inherited += 1
        except Exception:
            pass

    if inherited:
        logger.info(f"[Workflow:Discovery] Inherited {inherited} URLs from prior business docs")
    return discovered


async def _find_missing_websites(discovered: list[dict]) -> list[dict]:
    """Search for websites of businesses that still have no URL after inheritance."""
    from hephae_api.workflows.phases.enrichment import _find_website

    missing = [b for b in discovered if not b.get("officialUrl")]
    if not missing:
        return discovered

    logger.info(f"[Workflow:Discovery] Searching for websites of {len(missing)} businesses without URLs")

    async def _search_one(biz: dict):
        try:
            url = await _find_website(biz["name"], biz.get("address", ""))
            if url:
                biz["officialUrl"] = url
                logger.info(f"[Workflow:Discovery] Found website for {biz['name']}: {url}")
        except Exception as e:
            logger.warning(f"[Workflow:Discovery] Website search failed for {biz['name']}: {e}")

    # Run searches concurrently (max 5 at a time to avoid rate limits)
    sem = asyncio.Semaphore(5)
    async def _bounded(biz):
        async with sem:
            await _search_one(biz)

    await asyncio.gather(*[_bounded(b) for b in missing], return_exceptions=True)

    found = sum(1 for b in missing if b.get("officialUrl"))
    logger.info(f"[Workflow:Discovery] Website search found {found}/{len(missing)} URLs")
    return discovered


def to_business_workflow_states(discovered: list[dict]) -> list[BusinessWorkflowState]:
    """Convert discovered businesses to BusinessWorkflowState objects."""
    return [
        BusinessWorkflowState(
            slug=biz["slug"],
            name=biz["name"],
            address=biz.get("address", ""),
            officialUrl=biz.get("officialUrl"),
            sourceZipCode=biz.get("sourceZipCode"),
            businessType=biz.get("businessType"),
            phase=BusinessPhase.PENDING,
        )
        for biz in discovered
    ]
