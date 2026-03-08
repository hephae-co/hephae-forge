"""Enrichment phase — calls discovery runner for business profile enrichment (no HTTP)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def enrich_business_profile(
    name: str, address: str, slug: str
) -> dict | None:
    """Enrich a business profile via direct runner call (in-process, no HTTP)."""
    try:
        from hephae_capabilities.discovery.runner import run_discovery
        from hephae_db.firestore.businesses import get_business

        # Load existing business data to get website URL
        biz_data = await get_business(slug)
        website = (biz_data or {}).get("website", "") if biz_data else ""

        # If no website, try a Google search-based enrichment
        if not website:
            logger.warning(f"[Enrichment] No website for {slug}, attempting search-based discovery")
            website = await _find_website(name, address)

        if not website:
            logger.warning(f"[Enrichment] Could not find website for {slug}, skipping full discovery")
            # Return basic enrichment from scanner data
            return biz_data if biz_data else None

        identity = {
            "name": name,
            "address": address,
            "officialUrl": website,
        }
        result = await run_discovery(identity)

        if result and isinstance(result, dict):
            logger.info(f"[Enrichment] Enriched profile for {slug}")
            return result

        logger.warning(f"[Enrichment] No enrichment data for {slug}")
        return None
    except Exception as e:
        logger.error(f"[Enrichment] Failed for {slug}: {e}")
        return None


async def _find_website(name: str, address: str) -> str:
    """Try to find a business website using Google Search via ADK."""
    try:
        from hephae_common.adk_helpers import run_agent_to_json
        from hephae_common.model_config import AgentModels
        from google.adk.agents import LlmAgent
        from google.adk.tools import google_search

        agent = LlmAgent(
            name="WebsiteFinder",
            model=AgentModels.PRIMARY_MODEL,
            instruction="""Find the official website URL for the given business.
            Use Google Search to find it. Return ONLY a JSON object with a single "url" field.
            Example: {"url": "https://example.com"}
            If you cannot find a website, return: {"url": ""}""",
            tools=[google_search],
        )

        data = await run_agent_to_json(
            agent,
            f"Find the official website for: {name}, located at {address}",
            app_name="HephaeAdmin",
        )
        if data and isinstance(data, dict):
            return data.get("url", "")
    except Exception as e:
        logger.warning(f"[Enrichment] Website search failed for {name}: {e}")
    return ""
