"""POST /api/discover — Full business discovery pipeline."""

from __future__ import annotations

import asyncio
import logging
import traceback

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_request, optional_firebase_user

from hephae_capabilities.discovery.runner import run_discovery
from backend.config import AgentVersions
from hephae_common.report_storage import generate_slug, upload_report, upload_menu_screenshot, upload_menu_html
from hephae_common.report_templates import build_profile_report
from hephae_db.firestore.discovery import write_discovery
from hephae_db.firestore.agent_results import write_agent_result
from backend.types import EnrichedProfile as EnrichedProfileModel

logger = logging.getLogger(__name__)

router = APIRouter()


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
async def discover(request: Request, firebase_user: dict | None = Depends(optional_firebase_user)):
    try:
        body = await request.json()
        identity = body.get("identity")

        if not identity or not identity.get("name"):
            return JSONResponse({"error": "Missing BaseIdentity (name required)"}, status_code=400)

        name = identity.get("name", "Unknown")
        logger.info(f"[API/Discover] Running DiscoveryPipeline for: {name}")

        # Use the canonical runner — includes entity match abort, local context
        # enrichment, context caching, challenges, and all P0 improvements
        enriched_profile = await run_discovery(identity)

        logger.info(f"[API/Discover] Pipeline finished for: {name}")

        # Early exit if discovery was aborted (entity mismatch)
        if enriched_profile.get("discoveryAborted"):
            logger.warning(
                f"[API/Discover] Discovery aborted for {name}: "
                f"{enriched_profile.get('discoveryAbortReason', 'unknown')}"
            )
            return JSONResponse(enriched_profile)

        slug = generate_slug(name)

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

        # Link business to authenticated user (fire-and-forget)
        if firebase_user and firebase_user.get("uid"):
            from hephae_db.firestore.users import add_business_to_user
            asyncio.create_task(
                asyncio.to_thread(add_business_to_user, firebase_user["uid"], slug)
            )

        # Write social profiler metrics as agent result (fire-and-forget)
        social_profile_metrics = enriched_profile.get("socialProfileMetrics")
        if social_profile_metrics:
            summary_data = social_profile_metrics.get("summary", {}) if isinstance(social_profile_metrics, dict) else {}
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
        validation_report = enriched_profile.get("validationReport")
        if validation_report:
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="discovery_reviewer",
                    agent_version=AgentVersions.DISCOVERY_REVIEWER,
                    triggered_by="user",
                    raw_data={"validationReport": validation_report},
                    summary=(
                        f"Checked {validation_report.get('totalUrlsChecked', 0)} URLs: "
                        f"{validation_report.get('valid', 0)} valid, "
                        f"{validation_report.get('invalid', 0)} invalid, "
                        f"{validation_report.get('corrected', 0)} corrected"
                    ),
                )
            )

        # Write news discovery results (fire-and-forget)
        news = enriched_profile.get("news")
        if news:
            asyncio.create_task(
                write_agent_result(
                    business_slug=slug,
                    business_name=name,
                    agent_name="news_discovery",
                    agent_version=AgentVersions.NEWS_DISCOVERY,
                    triggered_by="user",
                    raw_data=news,
                    summary=f"Found {len(news)} news mentions",
                )
            )

        # Write AI overview results (fire-and-forget)
        ai_overview = enriched_profile.get("aiOverview")
        if ai_overview and isinstance(ai_overview, dict):
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
