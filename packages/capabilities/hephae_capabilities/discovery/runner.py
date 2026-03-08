"""Discovery runner — stateless async function.

Runs the full discovery pipeline and returns an enriched profile dict.
"""

from __future__ import annotations

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

from hephae_capabilities.discovery.agent import discovery_pipeline

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


async def run_discovery(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the full discovery pipeline.

    Args:
        identity: Base identity dict (must have officialUrl).
        business_context: Unused.

    Returns:
        Enriched profile dict with socialLinks, competitors, theme, etc.
    """
    if not identity.get("officialUrl"):
        raise ValueError("Missing officialUrl for discovery")

    name = identity.get("name", "Unknown")
    logger.info(f"[Discovery Runner] Running for: {name}")

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="hephae-hub",
        agent=discovery_pipeline,
        session_service=session_service,
    )

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

    async for _ in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(prompt),
    ):
        pass

    final_session = await session_service.get_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id
    )
    state = final_session.state if final_session else {}

    logger.info(f"[Discovery Runner] Pipeline Finished. State keys: {list(state.keys())}")

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

    # Parse reviewer output (Stage 4) and news data (Stage 2)
    reviewer_data = _safe_parse(state.get("reviewerData"))
    news_data = _safe_parse_array(state.get("newsData"))

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
        "validationReport": validation_report,
    }

    return enriched_profile
