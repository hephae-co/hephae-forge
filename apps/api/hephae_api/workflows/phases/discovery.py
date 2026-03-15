"""Discovery phase — finds businesses via scan_zipcode (Google Search + OSM).

Implements incremental discovery: loads existing businesses from Firestore first,
then runs fresh discovery to find NEW businesses, and merges both sets.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable

from hephae_agents.discovery.zipcode_scanner import scan_zipcode
from hephae_db.firestore.businesses import get_business, get_businesses_by_zip_and_category
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

    Incremental discovery:
    1. Load existing businesses from Firestore for this zip + type
    2. Run fresh discovery with exclusion list (known names) to find NEW businesses
    3. Merge existing + new, deduped by slug
    """
    logger.info(f"[Workflow:Discovery] Discovering {business_type} in {zip_code}")

    # 1. Load existing businesses from Firestore
    existing_docs = await get_businesses_by_zip_and_category(zip_code, business_type)
    existing_by_slug: dict[str, dict] = {}
    known_names: list[str] = []
    for doc in existing_docs:
        slug = doc.get("docId") or doc.get("id") or generate_slug(doc.get("name", ""))
        if slug and slug not in existing_by_slug:
            existing_by_slug[slug] = {
                "slug": slug,
                "name": doc.get("name", ""),
                "address": doc.get("address", ""),
                "officialUrl": doc.get("officialUrl") or doc.get("website"),
                "sourceZipCode": zip_code,
                "businessType": business_type,
            }
            known_names.append(doc.get("name", ""))

    logger.info(f"[Workflow:Discovery] Found {len(existing_by_slug)} existing businesses in Firestore for {zip_code}/{business_type}")

    # 2. Run fresh discovery — pass known names so ADK agent searches for NEW ones
    results = await scan_zipcode(zip_code, category=business_type, force=True, known_names=known_names if known_names else None)

    # 3. Merge: start with existing, add newly discovered
    merged = dict(existing_by_slug)  # copy
    new_count = 0
    for biz in results:
        slug = biz.docId or generate_slug(biz.name)
        if slug not in merged:
            merged[slug] = {
                "slug": slug,
                "name": biz.name,
                "address": biz.address,
                "officialUrl": getattr(biz, "website", None),
                "sourceZipCode": zip_code,
                "businessType": business_type,
            }
            new_count += 1

    logger.info(f"[Workflow:Discovery] Merged: {len(existing_by_slug)} existing + {new_count} new = {len(merged)} total")
    return list(merged.values())


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
