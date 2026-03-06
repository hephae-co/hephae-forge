"""Enrichment phase — calls hephae-forge /api/v1/discover for business profile enrichment."""

from __future__ import annotations

import logging

import httpx

from backend.config import settings
from backend.lib.forge_auth import forge_api_key_headers

logger = logging.getLogger(__name__)


async def enrich_business_profile(
    name: str, address: str, slug: str
) -> dict | None:
    """Call hephae-forge /api/v1/discover to enrich a business profile.

    Returns enriched profile dict or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.FORGE_URL}/api/v1/discover",
                json={"query": f"{name} {address}"},
                headers=forge_api_key_headers(),
            )

        if resp.status_code == 200:
            result = resp.json()
            if result.get("success") and result.get("data"):
                enriched = result["data"]
                logger.info(f"[Enrichment] Enriched profile for {slug}")
                return enriched

        logger.warning(f"[Enrichment] No enrichment data for {slug}")
        return None
    except Exception as e:
        logger.error(f"[Enrichment] Failed for {slug}: {e}")
        return None
