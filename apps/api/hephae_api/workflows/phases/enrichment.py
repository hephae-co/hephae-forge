"""Enrichment phase — calls discovery runner for business profile enrichment (no HTTP)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def enrich_business_profile(
    name: str, address: str, slug: str
) -> dict | None:
    """Enrich a business profile via direct runner call (in-process, no HTTP)."""
    try:
        from hephae_agents.discovery.runner import run_discovery
        from hephae_db.firestore.businesses import get_business

        # Load existing business data to get website URL
        biz_data = await get_business(slug)
        website = (
            (biz_data or {}).get("officialUrl")
            or (biz_data or {}).get("website")
            or (biz_data or {}).get("identity", {}).get("officialUrl")
            or ""
        ) if biz_data else ""

        # If no website, try a Google search-based enrichment
        if not website:
            logger.warning(f"[Enrichment] No website for {slug}, attempting search-based discovery")
            website = await _find_website(name, address)
            # Persist found URL immediately so it survives even if discovery fails
            if website:
                from hephae_db.firestore.businesses import save_business
                await save_business(slug, {"officialUrl": website})
                logger.info(f"[Enrichment] Found and saved website for {slug}: {website}")

        identity = {
            "name": name,
            "address": address,
            "officialUrl": website or "",
        }

        if not website:
            logger.info(f"[Enrichment] No website for {slug}, running search-based discovery")
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
    """Try to find a business website using Google Search via ADK. Retries on 429."""
    import asyncio

    for attempt in range(2):
        try:
            from hephae_common.adk_helpers import run_agent_to_json
            from hephae_common.model_config import AgentModels
            from hephae_common.model_fallback import fallback_on_error
            from google.adk.agents import LlmAgent
            from google.adk.tools import google_search

            agent = LlmAgent(
                name="WebsiteFinder",
                model=AgentModels.PRIMARY_MODEL,
                instruction="""You are a business website finder. Your job is to find the official website URL for a local business.

Search strategy — try MULTIPLE searches to maximize your chances:
1. Search for the exact business name + city (e.g., "Queen Margherita Trattoria Nutley")
2. Search for the business name + "official website" (e.g., "Sugar Tree Cafe official website")
3. Search for the business name + "menu" or "hours" if it's a restaurant

Look for the business's OWN domain (e.g., sugartreecafe.com, bellalucenj.com), NOT a Yelp/Facebook/TripAdvisor/Google Maps page.

IMPORTANT: Many small businesses have websites. Try hard before giving up. If a business has a Facebook page, it likely has a website too.

Return ONLY a JSON object: {"url": "https://example.com"} or {"url": ""} if truly not found.""",
                tools=[google_search],
                on_model_error_callback=fallback_on_error,
            )

            data = await run_agent_to_json(
                agent,
                f'Find the official website for "{name}" located at {address}. Search for "{name}" + the city name.',
                app_name="HephaeAdmin",
            )
            if data and isinstance(data, dict):
                url = data.get("url", "")
                if url:
                    return url
        except Exception as e:
            is_retriable = "429" in str(e) or "Resource exhausted" in str(e) or "503" in str(e)
            if is_retriable and attempt < 1:
                logger.warning(f"[Enrichment] Website search attempt {attempt + 1} failed for {name}: {e}, retrying...")
                await asyncio.sleep(10)
                continue
            logger.warning(f"[Enrichment] Website search failed for {name}: {e}")
    return ""
