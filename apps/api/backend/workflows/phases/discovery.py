"""Discovery phase — finds businesses via scan_zipcode (Google Search + OSM)."""

from __future__ import annotations

import logging
import re
from typing import Callable

from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode
from backend.types import BusinessWorkflowState, BusinessPhase

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
    results = await scan_zipcode(zip_code, force=True)

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
