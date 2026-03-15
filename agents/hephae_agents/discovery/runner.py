"""Discovery runner — stateless async function.

Runs the full discovery pipeline and returns an enriched profile dict.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels
from hephae_common.adk_helpers import user_msg

from hephae_agents.discovery.agent import discovery_phase1, discovery_phase2

logger = logging.getLogger(__name__)


def _safe_parse(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        return json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
    except (json.JSONDecodeError, ValueError):
        return {}


def _safe_parse_array(value) -> list:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _extract_zip_code(identity: dict[str, Any]) -> str | None:
    """Extract zip code from identity.zipCode or parse from address."""
    zc = identity.get("zipCode") or identity.get("zip_code") or identity.get("zip")
    if zc:
        return str(zc).strip()[:5]
    addr = identity.get("address", "")
    if addr:
        m = re.search(r"\b(\d{5})(?:-\d{4})?\b", addr)
        if m:
            return m.group(1)
    return None


async def _fetch_local_context(zip_code: str | None) -> dict[str, Any] | None:
    """Fetch area and zipcode research for a zip code. Returns None if unavailable."""
    if not zip_code:
        return None
    try:
        from hephae_db.context.admin_data import get_area_research_for_zip, get_zipcode_report

        area_res, zip_res = await asyncio.gather(
            get_area_research_for_zip(zip_code),
            get_zipcode_report(zip_code),
        )
        if area_res or zip_res:
            logger.info(f"[Discovery Runner] Local context found for {zip_code}")
            return {
                "areaResearch": area_res,
                "zipcodeResearch": zip_res,
            }
    except Exception as e:
        logger.warning(f"[Discovery Runner] Local context fetch failed for {zip_code}: {e}")
    return None


async def run_discovery(
    identity: dict[str, Any],
    business_context: Any | None = None,
    stages: list[int] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the full discovery pipeline with optional stage filtering.

    Args:
        identity: Base identity dict (must have officialUrl).
        business_context: Unused.
        stages: Optional list of phases to run (e.g. [1] for Phase 1 only).

    Returns:
        Enriched profile dict with socialLinks, competitors, theme, etc.
    """
    has_url = bool(identity.get("officialUrl"))
    name = identity.get("name", "Unknown")
    logger.info(f"[Discovery Runner] Running for: {name} (URL: {has_url}, Stages: {stages or 'ALL'})")

    from hephae_db.firestore.session_service import FirestoreSessionService
    session_service = FirestoreSessionService()
    session_id = f"discovery-{int(time.time() * 1000)}"
    user_id = "hub-user"

    await session_service.create_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id, state={}
    )

    prompt = f"""
        Please discover everything about this business:
        Name: {name}
        Address: {identity.get("address", "")}
        URL: {identity.get("officialUrl", "")}
    """

    # --- Phase 1: Crawl + entity validation (parallel with local context fetch) ---
    zip_code = _extract_zip_code(identity)
    p1_state: dict[str, Any] = {}
    local_context: dict[str, Any] | None = None

    # Load grounding memory from human-curated fixtures
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("discovery")

    if has_url:
        async def _run_phase1():
            phase1_runner = Runner(
                app_name="hephae-hub",
                agent=discovery_phase1,
                session_service=session_service,
                memory_service=memory_service,
            )
            async for _ in phase1_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_msg(prompt),
            ):
                pass

        # Fire Phase 1 crawl and local context fetch in parallel — context fetch
        # (~200ms Firestore read) is hidden behind the crawl's 5-15s network I/O
        results = await asyncio.gather(
            _run_phase1(),
            _fetch_local_context(zip_code),
            return_exceptions=True,
        )
        # Handle Phase 1 errors gracefully — log and continue with empty state
        if isinstance(results[0], BaseException):
            logger.error(f"[Discovery Runner] Phase 1 failed for {name}: {results[0]}")
        local_context = results[1] if not isinstance(results[1], BaseException) else None

        p1_session = await session_service.get_session(
            app_name="hephae-hub", user_id=user_id, session_id=session_id
        )
        p1_state = p1_session.state if p1_session else {}
    else:
        # No website — skip Phase 1 (crawl + entity match), just fetch local context
        logger.info(f"[Discovery Runner] No URL for {name} — skipping Phase 1, running Phase 2 only")
        local_context = await _fetch_local_context(zip_code)

    # JIT: If only Phase 1 was requested, return early
    if stages is not None and 2 not in stages:
        logger.info("[Discovery Runner] JIT Early Exit: Phase 1 complete.")
        return {**identity, "identity": p1_state}

    raw_content = p1_state.get("rawSiteData", "")

    # P0.1: Create Gemini Context Cache for Phase 2 (8 parallel agents)
    cache_name = None
    if raw_content and len(raw_content) > 2048:
        try:
            from hephae_common.gemini_cache import get_or_create_cache
            class DiscoveryContext:
                def __init__(self, slug, text):
                    self.slug = slug
                    self.text = text
                def to_prompt_context(self): return self.text
            
            cache_ctx = DiscoveryContext(f"disc-{int(time.time())}", raw_content)
            cache_name = await get_or_create_cache(cache_ctx, AgentModels.PRIMARY_MODEL)
            if cache_name:
                logger.info(f"[Discovery Runner] Context Cached: {cache_name}")
                # Inject cache name into session state for ADK to pick up
                await session_service.update_session(
                    app_name="hephae-hub", 
                    user_id=user_id, 
                    session_id=session_id,
                    state={"gemini_cache_name": cache_name}
                )
        except Exception as e:
            logger.warning(f"[Discovery Runner] Caching failed: {e}")

    # P0.3: Check entity match — abort early on MISMATCH/AGGREGATOR (skip if no URL)
    entity_match = _safe_parse(p1_state.get("entityMatchResult")) if has_url else {}
    match_status = entity_match.get("status", "MATCH")
    if has_url and match_status in ("MISMATCH", "AGGREGATOR"):
        logger.warning(
            f"[Discovery Runner] Entity mismatch for {name}: status={match_status}, "
            f"reason={entity_match.get('reason', 'unknown')}"
        )
        return {
            **identity,
            "entityMatch": entity_match,
            "discoveryAborted": True,
            "discoveryAbortReason": f"Site does not match target business: {entity_match.get('reason', match_status)}",
        }

    # --- Phase 2: Full research (entity match passed) ---
    logger.info(f"[Discovery Runner] Entity match passed ({match_status}). Running full research.")
    phase2_runner = Runner(
        app_name="hephae-hub",
        agent=discovery_phase2,
        session_service=session_service,
        memory_service=memory_service,
    )
    async for _ in phase2_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg("Continue with full discovery research."),
    ):
        pass

    final_session = await session_service.get_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id
    )
    state = final_session.state if final_session else {}

    # Parse each sub-agent output
    theme_data = _safe_parse(state.get("themeData"))
    contact_data = _safe_parse(state.get("contactData"))
    social_data = _safe_parse(state.get("socialData"))
    menu_data = _safe_parse(state.get("menuData"))
    social_profile_metrics = _safe_parse(state.get("socialProfileMetrics"))
    ai_overview = _safe_parse(state.get("aiOverview"))
    maps_url = state.get("mapsData", "")
    if isinstance(maps_url, str):
        maps_url = re.sub(r"```json\n?|\n?```", "", maps_url).replace('"', "").strip()

    # Parse competitors with Gemini extraction fallback
    parsed_competitors = _safe_parse_array(state.get("competitorData"))
    if (
        not parsed_competitors
        and isinstance(state.get("competitorData"), str)
        and len(state["competitorData"].strip()) > 10
    ):
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                client = genai.Client(api_key=api_key)
                res = await client.aio.models.generate_content(
                    model=AgentModels.PRIMARY_MODEL,
                    contents=(
                        f'Extract exactly 3 restaurant competitors from the following text into a JSON array '
                        f'with keys: "name", "url", "reason". TEXT: {state["competitorData"]}'
                    ),
                    config={"response_mime_type": "application/json"},
                )
                parsed_competitors = json.loads(res.text)
        except Exception as e:
            logger.error(f"[Discovery Runner] Forced extraction failed: {e}")

    th = theme_data
    sd = social_data
    md = menu_data
    cd = contact_data

    # Parse reviewer output (Stage 4), news data (Stage 2), and challenges data (P0.2)
    reviewer_data = _safe_parse(state.get("reviewerData"))
    news_data = _safe_parse_array(state.get("newsData"))
    challenges_data = _safe_parse(state.get("challengesData"))

    # If reviewer ran, use validated data as authoritative
    vs = reviewer_data.get("validatedSocialData", {}) if reviewer_data else {}
    validated_menu = reviewer_data.get("validatedMenuUrl") if reviewer_data else None
    validated_competitors = reviewer_data.get("validatedCompetitors", []) if reviewer_data else []
    validated_news = reviewer_data.get("validatedNews", []) if reviewer_data else []
    validated_maps = reviewer_data.get("validatedMapsUrl") if reviewer_data else None
    validation_report = reviewer_data.get("validationReport") if reviewer_data else None

    enriched_profile = {
        **identity,
        "menuUrl": (validated_menu if validated_menu is not None else md.get("menuUrl")) or None,
        "socialLinks": {
            "instagram": vs.get("instagram") or sd.get("instagram") or None,
            "facebook": vs.get("facebook") or sd.get("facebook") or None,
            "twitter": vs.get("twitter") or sd.get("twitter") or None,
            "yelp": vs.get("yelp") or sd.get("yelp") or None,
            "tiktok": vs.get("tiktok") or sd.get("tiktok") or None,
            "grubhub": vs.get("grubhub") or md.get("grubhub") or sd.get("grubhub") or None,
            "doordash": vs.get("doordash") or md.get("doordash") or sd.get("doordash") or None,
            "ubereats": vs.get("ubereats") or md.get("ubereats") or sd.get("ubereats") or None,
            "seamless": vs.get("seamless") or md.get("seamless") or sd.get("seamless") or None,
            "toasttab": vs.get("toasttab") or md.get("toasttab") or sd.get("toasttab") or None,
        },
        "phone": cd.get("phone") or sd.get("phone") or None,
        "email": cd.get("email") or sd.get("email") or None,
        "emailStatus": cd.get("emailStatus") or None,
        "contactFormUrl": cd.get("contactFormUrl") or None,
        "contactFormStatus": cd.get("contactFormStatus") or None,
        "hours": cd.get("hours") or sd.get("hours") or None,
        "googleMapsUrl": validated_maps or maps_url or None,
        "competitors": validated_competitors if validated_competitors else (parsed_competitors if parsed_competitors else None),
        "news": validated_news if validated_news else (news_data if news_data else None),
        "favicon": th.get("favicon") or None,
        "logoUrl": th.get("logoUrl") or None,
        "primaryColor": th.get("primaryColor") or None,
        "secondaryColor": th.get("secondaryColor") or None,
        "persona": th.get("persona") or None,
        "socialProfileMetrics": social_profile_metrics or None,
        "aiOverview": ai_overview or None,
        "challenges": challenges_data or None,
        "entityMatch": entity_match or None,
        "validationReport": validation_report,
        "localContext": local_context,
    }

    return enriched_profile
