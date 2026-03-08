"""POST /api/discover — Full business discovery pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import traceback

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_request

from hephae_capabilities.discovery import discovery_pipeline
from backend.config import AgentModels, AgentVersions
from hephae_common.report_storage import generate_slug, upload_report, upload_menu_screenshot, upload_menu_html
from hephae_common.report_templates import build_profile_report
from hephae_db.firestore.discovery import write_discovery
from hephae_db.firestore.agent_results import write_agent_result
from hephae_common.adk_helpers import user_msg
from backend.types import EnrichedProfile as EnrichedProfileModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _safe_parse(value) -> dict:
    """Safely parse a JSON string, stripping markdown fences."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        return json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
    except (json.JSONDecodeError, ValueError):
        return {}


def _safe_parse_array(value) -> list:
    """Safely parse a JSON array string."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


async def _capture_menu(menu_url: str, slug: str) -> tuple[str, str]:
    """Capture menu page as screenshot + HTML, upload both to GCS.

    Returns (screenshot_url, html_url).  Either may be empty on failure.
    """
    from hephae_capabilities.shared_tools import screenshot_page

    result = await screenshot_page(menu_url)
    screenshot_url = ""
    html_url = ""
    if result.get("screenshot_base64"):
        screenshot_url = await upload_menu_screenshot(slug, result["screenshot_base64"])
    if result.get("html"):
        html_url = await upload_menu_html(slug, result["html"])
    return screenshot_url, html_url


@router.post("/discover", response_model=EnrichedProfileModel, dependencies=[Depends(verify_request)])
async def discover(request: Request):
    try:
        body = await request.json()
        identity = body.get("identity")

        if not identity or not identity.get("officialUrl"):
            return JSONResponse({"error": "Missing BaseIdentity"}, status_code=400)

        name = identity.get("name", "Unknown")
        logger.info(f"[API/Discover] Running DiscoveryPipeline for: {name}")

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="hephae-hub",
            agent=discovery_pipeline,
            session_service=session_service,
        )

        session_id = f"discovery-{int(time.time() * 1000)}"
        user_id = "hub-user"

        await session_service.create_session(
            app_name="hephae-hub",
            user_id=user_id,
            session_id=session_id,
            state={},
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

        logger.info(f"[API/Discover] Pipeline Finished. State keys: {list(state.keys())}")

        # Parse each sub-agent output
        theme_data = _safe_parse(state.get("themeData"))
        contact_data = _safe_parse(state.get("contactData"))
        social_data = _safe_parse(state.get("socialData"))
        menu_data = _safe_parse(state.get("menuData"))
        social_profile_metrics = _safe_parse(state.get("socialProfileMetrics"))
        ai_overview = _safe_parse(state.get("aiOverview"))
        maps_url = state.get("mapsData", "")
        if isinstance(maps_url, str):
            maps_url = re.sub(r'```json\n?|\n?```', "", maps_url).replace('"', "").strip()

        # Parse competitors with Gemini extraction fallback
        parsed_competitors = _safe_parse_array(state.get("competitorData"))
        if not parsed_competitors and isinstance(state.get("competitorData"), str) and len(state["competitorData"].strip()) > 10:
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
                logger.error(f"[API/Discover] Forced extraction failed: {e}")

        th = theme_data
        sd = social_data
        md = menu_data
        cd = contact_data

        # Parse reviewer output (Stage 4) and news data (Stage 2)
        reviewer_data = _safe_parse(state.get("reviewerData"))
        news_data = _safe_parse_array(state.get("newsData"))
        validation_report = None

        # If reviewer ran, use validated data as authoritative
        vs = reviewer_data.get("validatedSocialData", {}) if reviewer_data else {}
        validated_menu = reviewer_data.get("validatedMenuUrl") if reviewer_data else None
        validated_competitors = reviewer_data.get("validatedCompetitors", []) if reviewer_data else []
        validated_news = reviewer_data.get("validatedNews", []) if reviewer_data else []
        validated_maps = reviewer_data.get("validatedMapsUrl") if reviewer_data else None
        if reviewer_data:
            validation_report = reviewer_data.get("validationReport")
            logger.info(f"[API/Discover] Reviewer report: {validation_report}")

        slug = generate_slug(name)

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

        # Capture menu screenshot + HTML and upload to GCS
        menu_url = enriched_profile.get("menuUrl")
        if menu_url:
            screenshot_url, html_url = await _capture_menu(menu_url, slug)
            if screenshot_url:
                enriched_profile["menuScreenshotUrl"] = screenshot_url
            if html_url:
                enriched_profile["menuHtmlUrl"] = html_url

        # Upload HTML report to GCS
        report_url = await upload_report(
            slug=slug,
            report_type="profile",
            html_content=build_profile_report(enriched_profile),
            identity=enriched_profile,
            summary=f"Business profile for {name}",
        )

        # Write to Firestore + BQ (fire-and-forget)
        asyncio.create_task(
            write_discovery(
                profile=enriched_profile,
                triggered_by="user",
            )
        )

        # Write social profiler metrics as agent result (fire-and-forget)
        if social_profile_metrics:
            summary_data = social_profile_metrics.get("summary", {})
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="social_profiler",
                    agent_version=AgentVersions.SOCIAL_PROFILER,
                    triggered_by="user",
                    raw_data=social_profile_metrics,
                    score=summary_data.get("overallPresenceScore"),
                    summary=summary_data.get("recommendation", ""),
                )
            )

        # Write reviewer validation results (fire-and-forget)
        if validation_report:
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="discovery_reviewer",
                    agent_version=AgentVersions.DISCOVERY_REVIEWER,
                    triggered_by="user",
                    raw_data=reviewer_data,
                    summary=(
                        f"Checked {validation_report.get('totalUrlsChecked', 0)} URLs: "
                        f"{validation_report.get('valid', 0)} valid, "
                        f"{validation_report.get('invalid', 0)} invalid, "
                        f"{validation_report.get('corrected', 0)} corrected"
                    ),
                )
            )

        # Write news discovery results (fire-and-forget)
        news_to_store = validated_news if validated_news else news_data
        if news_to_store:
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="news_discovery",
                    agent_version=AgentVersions.NEWS_DISCOVERY,
                    triggered_by="user",
                    raw_data=news_to_store,
                    summary=f"Found {len(news_to_store)} news mentions",
                )
            )

        # Write AI overview results (fire-and-forget)
        if ai_overview:
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="business_overview",
                    agent_version=AgentVersions.BUSINESS_OVERVIEW,
                    triggered_by="user",
                    raw_data=ai_overview,
                    summary=(ai_overview.get("summary", "") or "")[:200],
                )
            )

        result = {**enriched_profile}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"[API/Discover] Orchestration Failed: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
