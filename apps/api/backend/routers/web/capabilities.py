"""Consolidated capabilities router — SEO, Competitive, Traffic, Marketing (Social Audit).

Merges:
  - POST /api/capabilities/seo
  - POST /api/capabilities/competitive
  - POST /api/capabilities/traffic
  - POST /api/capabilities/marketing
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_request

from hephae_capabilities.seo_auditor import seo_auditor_agent
from hephae_capabilities.seo_auditor.prompt import SEO_AUDITOR_INSTRUCTION
from hephae_capabilities.seo_auditor.tools import pagespeed_tool
from hephae_capabilities.shared_tools import google_search_tool
from hephae_capabilities.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_capabilities.competitive_analysis import (
    competitor_profiler_agent,
    market_positioning_agent,
)
from hephae_capabilities.traffic_forecaster import ForecasterAgent
from hephae_capabilities.social.media_auditor import (
    social_researcher_agent,
    social_strategist_agent,
)
from hephae_common.report_storage import generate_slug, upload_report
from hephae_common.report_templates import (
    build_seo_report,
    build_competitive_report,
    build_traffic_report,
    build_social_audit_report,
)
from hephae_db.firestore.agent_results import write_agent_result
from hephae_db.context.business_context import build_business_context
from backend.config import AgentModels, AgentVersions
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from backend.types import (
    SeoReport as SeoReportModel,
    CompetitiveReport as CompetitiveReportModel,
    ForecastResponse as ForecastResponseModel,
    SocialAuditReport as SocialAuditReportModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["capabilities"])


# ─── SEO helpers ────────────────────────────────────────────────────────────────


def _try_extract_json(source: str, label: str) -> dict | None:
    """Try to extract JSON object from a text source."""
    if not source:
        return None
    raw = re.sub(r"```json\s*", "", source)
    raw = re.sub(r"```\s*", "", raw).strip()
    fb = raw.find("{")
    lb = raw.rfind("}")
    if fb == -1 or lb <= fb:
        return None
    raw = raw[fb : lb + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try removing trailing commas
        try:
            return json.loads(re.sub(r",\s*([\]}])", r"\1", raw))
        except json.JSONDecodeError:
            return None


def _is_final_response(event) -> bool:
    """Check if an ADK event is a final response (no function calls/responses)."""
    content = getattr(event, "content", None)
    if not content or not hasattr(content, "parts"):
        return False
    for part in content.parts:
        if hasattr(part, "function_call") and part.function_call:
            return False
        if hasattr(part, "function_response") and part.function_response:
            return False
    return True


def _has_valid_sections(report_data: dict) -> bool:
    """Return True if report_data has at least 1 section with a non-zero score."""
    sections = report_data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        return False
    return any(isinstance(s, dict) and s.get("score", 0) > 0 for s in sections)


async def _run_seo_agent(agent, identity: dict) -> dict:
    """Run an SEO auditor agent and return the parsed report data (or {})."""
    session_service = InMemorySessionService()
    runner = Runner(app_name="hephae-hub", agent=agent, session_service=session_service)

    session_id = f"seo-{int(time.time() * 1000)}"
    user_id = "hub-user"

    await session_service.create_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id, state={}
    )

    text_buffer = ""
    final_response_text = ""
    thought_buffer = ""

    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(
            f"Execute a full SEO Deep Dive on {identity['officialUrl']}. "
            "Evaluate technical SEO, content quality, user experience, performance, and backlinks."
        ),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    if getattr(part, "text", None):
                        thought_buffer += part.text
                    continue
                if getattr(part, "text", None):
                    text_buffer += part.text

            if _is_final_response(raw_event):
                for part in content.parts:
                    if getattr(part, "text", None) and not getattr(part, "thought", False):
                        final_response_text += part.text

    logger.info(
        f"[SEO API] Stream drained: buffer={len(text_buffer)} chars, "
        f"finalResponse={len(final_response_text)} chars, thought={len(thought_buffer)} chars"
    )

    return (
        _try_extract_json(final_response_text, "finalResponse")
        or _try_extract_json(text_buffer, "textBuffer")
        or _try_extract_json(thought_buffer, "thoughtBuffer")
        or {}
    )


# ─── SEO endpoint ──────────────────────────────────────────────────────────────


@router.post("/capabilities/seo", response_model=SeoReportModel, dependencies=[Depends(verify_request)])
async def capabilities_seo(request: Request):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["seo"])
        identity = ctx.identity

        if not identity.get("officialUrl"):
            return JSONResponse({"error": "No URL available for SEO Audit."}, status_code=400)

        logger.info(f"[SEO API] Launching SeoAuditorAgent for {identity['officialUrl']}...")

        # Primary run with ENHANCED_MODEL (gemini-3.0-flash)
        report_data = await _run_seo_agent(seo_auditor_agent, identity)

        # Fallback: if primary model returned empty/useless sections, retry with lite model
        if not _has_valid_sections(report_data):
            logger.warning(
                f"[SEO API] Primary model returned empty sections for {identity['officialUrl']}. "
                f"Retrying with fallback model {AgentModels.FALLBACK_LITE_MODEL}..."
            )
            fallback_agent = LlmAgent(
                name="seoAuditorFallback",
                description="SEO Auditor (fallback model)",
                instruction=SEO_AUDITOR_INSTRUCTION,
                model=AgentModels.ENHANCED_FALLBACK,
                tools=[google_search_tool, pagespeed_tool],
                on_model_error_callback=fallback_on_error,
            )
            fallback_data = await _run_seo_agent(fallback_agent, identity)
            if _has_valid_sections(fallback_data):
                report_data = fallback_data
                logger.info("[SEO API] Fallback model produced valid sections.")
            else:
                logger.warning("[SEO API] Fallback model also returned empty sections.")
                if fallback_data.get("overallScore"):
                    report_data = fallback_data

        if not report_data:
            logger.error("[SEO API] All JSON extraction failed.")

        # Mark sections as analyzed
        if isinstance(report_data.get("sections"), list):
            for section in report_data["sections"]:
                if not isinstance(section, dict):
                    continue
                section["isAnalyzed"] = True
                if not isinstance(section.get("recommendations"), list):
                    section["recommendations"] = []
                else:
                    # Filter out non-dict recommendations (LLM may return plain strings)
                    section["recommendations"] = [
                        r for r in section["recommendations"] if isinstance(r, dict)
                    ]

        final_report = {
            **report_data,
            "url": identity["officialUrl"],
            "sections": [s for s in report_data.get("sections", []) if isinstance(s, dict)] if isinstance(report_data.get("sections"), list) else [],
        }

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content({"identity": identity, "seo": final_report}, "SEO Deep Audit")
        )

        slug = generate_slug(identity.get("name") or identity["officialUrl"])

        report_url = await upload_report(
            slug=slug,
            report_type="seo",
            html_content=build_seo_report(final_report, identity=identity),
            identity=identity,
            summary=final_report.get("summary") or f"SEO score: {final_report.get('overallScore')}/100",
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity.get("name") or identity["officialUrl"],
                agent_name="seo_auditor",
                agent_version=AgentVersions.SEO_AUDITOR,
                triggered_by="user",
                score=final_report.get("overallScore"),
                summary=final_report.get("summary") or f"SEO score: {final_report.get('overallScore')}/100",
                report_url=report_url or None,
                raw_data=final_report,
            )
        )

        result = {**final_report}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[SEO API Error]: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─── Competitive endpoint ──────────────────────────────────────────────────────


@router.post("/capabilities/competitive", response_model=CompetitiveReportModel, dependencies=[Depends(verify_request)])
async def capabilities_competitive(request: Request):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["competitive"])
        identity = ctx.identity

        if not identity or not identity.get("competitors") or len(identity["competitors"]) == 0:
            return JSONResponse(
                {"error": "Missing competitors array. Please run discovery first."},
                status_code=400,
            )

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="competitive-analysis",
            agent=competitor_profiler_agent,
            session_service=session_service,
        )
        session_id = f"comp-{int(time.time() * 1000)}"
        user_id = "sys"

        await session_service.create_session(
            app_name="competitive-analysis", user_id=user_id, session_id=session_id, state={}
        )

        # Step 1: Profile Competitors
        logger.info("[API/Competitive] Step 1: Profiling Competitors...")

        # Build context-enriched prompt with admin data
        profiler_parts = [f"Research these competitors: {json.dumps(identity['competitors'])}"]
        if ctx.zipcode_research and isinstance(ctx.zipcode_research, dict):
            sections = ctx.zipcode_research.get("sections", {})
            if isinstance(sections, dict):
                if sections.get("demographics"):
                    profiler_parts.append(f"\n**LOCAL DEMOGRAPHICS (zip {ctx.zip_code}):**\n{json.dumps(sections['demographics'], default=str)[:2000]}")
                if sections.get("business_landscape"):
                    profiler_parts.append(f"\n**LOCAL BUSINESS LANDSCAPE:**\n{json.dumps(sections['business_landscape'], default=str)[:2000]}")
                if sections.get("consumer_market"):
                    profiler_parts.append(f"\n**CONSUMER MARKET:**\n{json.dumps(sections['consumer_market'], default=str)[:1500]}")
        if ctx.area_research and isinstance(ctx.area_research, dict):
            if ctx.area_research.get("competitiveLandscape"):
                profiler_parts.append(f"\n**AREA COMPETITIVE LANDSCAPE:**\n{json.dumps(ctx.area_research['competitiveLandscape'], default=str)[:1500]}")
            if ctx.area_research.get("demographicFit"):
                profiler_parts.append(f"\n**DEMOGRAPHIC FIT:**\n{json.dumps(ctx.area_research['demographicFit'], default=str)[:1000]}")

        profiler_prompt = "\n".join(profiler_parts)

        competitor_brief = ""
        async for raw_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(profiler_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        competitor_brief += part.text

        # Step 2: Market Positioning
        logger.info("[API/Competitive] Step 2: Running Market Strategy...")
        positioning_runner = Runner(
            app_name="competitive-analysis",
            agent=market_positioning_agent,
            session_service=session_service,
        )

        strategy_prompt = (
            f"TARGET RESTAURANT: {json.dumps(identity)}\n\n"
            f"COMPETITORS BRIEF:\n{competitor_brief}\n\n"
            "Generate the final competitive json report."
        )

        strategy_buffer = ""
        async for raw_event in positioning_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(strategy_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        strategy_buffer += part.text

        # Robust JSON extraction
        clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
        fb = clean_json_str.find("{")
        lb = clean_json_str.rfind("}")
        if fb != -1 and lb > fb:
            clean_json_str = clean_json_str[fb : lb + 1]
        payload = json.loads(clean_json_str)

        logger.info(f"[API/Competitive] Success: {list(payload.keys())}")

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "competitive": payload}, "Competitive Strategy"
            )
        )

        slug = generate_slug(identity.get("name", "unknown"))

        report_url = await upload_report(
            slug=slug,
            report_type="competitive",
            html_content=build_competitive_report(payload, identity),
            identity=identity,
            summary=payload.get("market_summary", "Competitive analysis complete"),
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity.get("name", "unknown"),
                agent_name="competitive_analyzer",
                agent_version=AgentVersions.COMPETITIVE_ANALYZER,
                triggered_by="user",
                summary=payload.get("market_summary", "Competitive analysis complete"),
                report_url=report_url or None,
                raw_data=payload,
            )
        )

        result = {**payload}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[API/Competitive] Failed: {exc}")
        return JSONResponse(
            {"error": str(exc) or "Failed to analyze competitors."},
            status_code=500,
        )


# ─── Traffic endpoint ──────────────────────────────────────────────────────────


@router.post("/capabilities/traffic", response_model=ForecastResponseModel, dependencies=[Depends(verify_request)])
async def capabilities_traffic(request: Request):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["traffic"])
        identity = ctx.identity

        if not identity or not identity.get("name"):
            return JSONResponse(
                {"error": "Missing Target Identity for Traffic Forecaster"},
                status_code=400,
            )

        forecast_data = await ForecasterAgent.forecast(identity, business_context=ctx)

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "forecast": forecast_data}, "Foot Traffic Heatmap"
            )
        )

        slug = generate_slug(identity["name"])

        report_url = await upload_report(
            slug=slug,
            report_type="traffic",
            html_content=build_traffic_report(forecast_data),
            identity=identity,
            summary=forecast_data.get("summary", ""),
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity["name"],
                agent_name="traffic_forecaster",
                agent_version=AgentVersions.TRAFFIC_FORECASTER,
                triggered_by="user",
                summary=forecast_data.get("summary", ""),
                report_url=report_url or None,
                raw_data=forecast_data,
            )
        )

        result = {**forecast_data}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[API/Capabilities/Traffic] Failed: {exc}")
        return JSONResponse({"error": str(exc) or "Internal Server Error"}, status_code=500)


# ─── Marketing (Social Audit) endpoint ─────────────────────────────────────────


@router.post("/capabilities/marketing", response_model=SocialAuditReportModel, dependencies=[Depends(verify_request)])
async def capabilities_marketing(request: Request):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["marketing"])
        identity = ctx.identity

        if not identity or not identity.get("name"):
            return JSONResponse(
                {"error": "Missing identity for Social Media Audit"},
                status_code=400,
            )

        business_name = identity["name"]
        logger.info(f"[Social Audit API] Running social media audit for {business_name}...")

        session_service = InMemorySessionService()
        session_id = f"social-audit-{int(time.time() * 1000)}"
        user_id = "sys"

        await session_service.create_session(
            app_name="social-audit", user_id=user_id, session_id=session_id, state={}
        )

        # -- Step 1: Social Researcher --
        logger.info("[Social Audit API] Step 1: Researching social presence...")

        researcher_parts = [f"Business: {business_name}"]
        if identity.get("address"):
            researcher_parts.append(f"Location: {identity['address']}")
        if identity.get("persona"):
            researcher_parts.append(f"Persona: {identity['persona']}")
        if identity.get("officialUrl"):
            researcher_parts.append(f"Website: {identity['officialUrl']}")

        # Inject known social links
        social = identity.get("socialLinks") or {}
        active_social = {k: v for k, v in social.items() if v}
        if active_social:
            researcher_parts.append(f"\nKNOWN SOCIAL LINKS:\n{json.dumps(active_social, indent=2)}")

        # Inject existing socialProfileMetrics from discovery (if available)
        spm = identity.get("socialProfileMetrics")
        if spm:
            researcher_parts.append(f"\nEXISTING DISCOVERY METRICS (comprehensive — focus on analysis and competitor benchmarking):\n{json.dumps(spm, default=str)[:3000]}")

        # Inject competitors for benchmarking
        competitors = identity.get("competitors", [])
        if competitors:
            researcher_parts.append(f"\nCOMPETITORS (research their social presence for benchmarking):\n{json.dumps(competitors[:5], default=str)}")

        researcher_prompt = "\n".join(researcher_parts)

        runner = Runner(
            app_name="social-audit",
            agent=social_researcher_agent,
            session_service=session_service,
        )

        research_brief = ""
        async for raw_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(researcher_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        research_brief += part.text

        # -- Step 2: Social Strategist --
        logger.info("[Social Audit API] Step 2: Synthesizing strategy...")

        strategist_runner = Runner(
            app_name="social-audit",
            agent=social_strategist_agent,
            session_service=session_service,
        )

        strategy_prompt = (
            f"TARGET BUSINESS: {json.dumps(identity, default=str)[:4000]}\n\n"
            f"SOCIAL MEDIA RESEARCH BRIEF:\n{research_brief}\n\n"
            "Generate the final social media audit JSON report."
        )

        strategy_buffer = ""
        async for raw_event in strategist_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(strategy_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        strategy_buffer += part.text

        # -- Parse JSON --
        clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
        fb = clean_json_str.find("{")
        lb = clean_json_str.rfind("}")
        if fb != -1 and lb > fb:
            clean_json_str = clean_json_str[fb : lb + 1]
        payload = json.loads(clean_json_str)

        logger.info(f"[Social Audit API] Success: score={payload.get('overall_score')}, platforms={len(payload.get('platforms', []))}")

        # -- Upload report + write result --
        slug = generate_slug(business_name)

        report_url = await upload_report(
            slug=slug,
            report_type="social-audit",
            html_content=build_social_audit_report(payload, identity),
            identity=identity,
            summary=payload.get("summary", "Social media audit complete"),
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=business_name,
                agent_name="social_media_auditor",
                agent_version=AgentVersions.SOCIAL_MEDIA_AUDITOR,
                triggered_by="user",
                summary=payload.get("summary", "Social media audit complete"),
                report_url=report_url or None,
                raw_data=payload,
            )
        )

        result = {**payload}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[Social Audit API Error]: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
