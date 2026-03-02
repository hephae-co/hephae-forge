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

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.discovery import discovery_pipeline
from backend.config import AgentVersions
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_profile_report
from backend.lib.db import write_discovery, write_agent_result
from backend.lib.adk_helpers import user_msg

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


@router.post("/discover")
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
                        model="gemini-2.5-flash",
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

        slug = generate_slug(name)

        enriched_profile = {
            **identity,
            "menuUrl": md.get("menuUrl") or None,
            "socialLinks": {
                "instagram": sd.get("instagram") or None,
                "facebook": sd.get("facebook") or None,
                "twitter": sd.get("twitter") or None,
                "yelp": sd.get("yelp") or None,
                "tiktok": sd.get("tiktok") or None,
                "grubhub": md.get("grubhub") or sd.get("grubhub") or None,
                "doordash": md.get("doordash") or sd.get("doordash") or None,
                "ubereats": md.get("ubereats") or sd.get("ubereats") or None,
                "seamless": md.get("seamless") or sd.get("seamless") or None,
                "toasttab": md.get("toasttab") or sd.get("toasttab") or None,
            },
            "phone": cd.get("phone") or sd.get("phone") or None,
            "email": cd.get("email") or sd.get("email") or None,
            "hours": cd.get("hours") or sd.get("hours") or None,
            "googleMapsUrl": maps_url or None,
            "competitors": parsed_competitors if parsed_competitors else None,
            "favicon": th.get("favicon") or None,
            "logoUrl": th.get("logoUrl") or None,
            "primaryColor": th.get("primaryColor") or None,
            "secondaryColor": th.get("secondaryColor") or None,
            "persona": th.get("persona") or None,
            "socialProfileMetrics": social_profile_metrics or None,
        }

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

        result = {**enriched_profile}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"[API/Discover] Orchestration Failed: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
