"""Consolidated capabilities router — SEO, Competitive, Traffic, Marketing (Social Audit).

Merges:
  - POST /api/capabilities/seo
  - POST /api/capabilities/competitive
  - POST /api/capabilities/traffic
  - POST /api/capabilities/marketing

All endpoints delegate to package runner functions (no manual Runner/session logic).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_request, optional_firebase_user

from hephae_agents.seo_auditor.runner import run_seo_audit
from hephae_agents.competitive_analysis.runner import run_competitive_analysis
from hephae_agents.social.media_auditor.runner import run_social_media_audit
from hephae_agents.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_agents.traffic_forecaster import ForecasterAgent
from hephae_common.report_storage import generate_slug, upload_report
from hephae_common.report_templates import (
    build_seo_report,
    build_competitive_report,
    build_traffic_report,
    build_social_audit_report,
)
from hephae_db.firestore.agent_results import write_agent_result
from hephae_db.context.business_context import build_business_context
from hephae_api.config import AgentVersions
from hephae_api.types import (
    SeoReport as SeoReportModel,
    CompetitiveReport as CompetitiveReportModel,
    ForecastResponse as ForecastResponseModel,
    SocialAuditReport as SocialAuditReportModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["capabilities"])


# ─── Shared helpers ───────────────────────────────────────────────────────────


def _fire_and_forget_persistence(
    slug: str,
    identity: dict,
    agent_name: str,
    agent_version: str,
    report_url: str | None,
    payload: dict,
    summary: str,
    firebase_user: dict | None,
):
    """Schedule report persistence tasks (non-blocking)."""
    if firebase_user and firebase_user.get("uid"):
        from hephae_db.firestore.users import add_business_to_user
        asyncio.create_task(asyncio.to_thread(add_business_to_user, firebase_user["uid"], slug))

    asyncio.create_task(
        write_agent_result(
            business_slug=slug,
            business_name=identity.get("name") or identity.get("officialUrl", "unknown"),
            agent_name=agent_name,
            agent_version=agent_version,
            triggered_by="user",
            score=payload.get("overallScore") or payload.get("overall_score"),
            summary=summary,
            report_url=report_url or None,
            raw_data=payload,
        )
    )


# ─── SEO endpoint ──────────────────────────────────────────────────────────────


@router.post("/capabilities/seo", response_model=SeoReportModel, dependencies=[Depends(verify_request)])
async def capabilities_seo(request: Request, firebase_user: dict | None = Depends(optional_firebase_user)):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["seo"])
        identity = ctx.identity

        if not identity.get("officialUrl"):
            return JSONResponse({"error": "No URL available for SEO Audit."}, status_code=400)

        logger.info(f"[SEO API] Launching runner for {identity['officialUrl']}...")

        final_report = await run_seo_audit(identity, business_context=ctx)

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content({"identity": identity, "seo": final_report}, "SEO Deep Audit")
        )

        slug = generate_slug(identity.get("name") or identity["officialUrl"])
        summary = final_report.get("summary") or f"SEO score: {final_report.get('overallScore')}/100"

        report_url = await upload_report(
            slug=slug,
            report_type="seo",
            html_content=build_seo_report(final_report, identity=identity),
            identity=identity,
            summary=summary,
        )

        _fire_and_forget_persistence(
            slug, identity, "seo_auditor", AgentVersions.SEO_AUDITOR,
            report_url, final_report, summary, firebase_user,
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
async def capabilities_competitive(request: Request, firebase_user: dict | None = Depends(optional_firebase_user)):
    try:
        body = await request.json()
        ctx = await build_business_context(body.get("identity", {}), capabilities=["competitive"])
        identity = ctx.identity

        if not identity or not identity.get("competitors") or len(identity["competitors"]) == 0:
            return JSONResponse(
                {"error": "Missing competitors array. Please run discovery first."},
                status_code=400,
            )

        logger.info(f"[Competitive API] Launching runner for {identity.get('name')}...")

        payload = await run_competitive_analysis(identity, business_context=ctx)

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "competitive": payload}, "Competitive Strategy"
            )
        )

        slug = generate_slug(identity.get("name", "unknown"))
        summary = payload.get("market_summary", "Competitive analysis complete")

        report_url = await upload_report(
            slug=slug,
            report_type="competitive",
            html_content=build_competitive_report(payload, identity),
            identity=identity,
            summary=summary,
        )

        _fire_and_forget_persistence(
            slug, identity, "competitive_analyzer", AgentVersions.COMPETITIVE_ANALYZER,
            report_url, payload, summary, firebase_user,
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
async def capabilities_traffic(request: Request, firebase_user: dict | None = Depends(optional_firebase_user)):
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
        summary = forecast_data.get("summary", "")

        report_url = await upload_report(
            slug=slug,
            report_type="traffic",
            html_content=build_traffic_report(forecast_data),
            identity=identity,
            summary=summary,
        )

        _fire_and_forget_persistence(
            slug, identity, "traffic_forecaster", AgentVersions.TRAFFIC_FORECASTER,
            report_url, forecast_data, summary, firebase_user,
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
async def capabilities_marketing(request: Request, firebase_user: dict | None = Depends(optional_firebase_user)):
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
        logger.info(f"[Social Audit API] Launching runner for {business_name}...")

        payload = await run_social_media_audit(identity, business_context=ctx)

        slug = generate_slug(business_name)
        summary = payload.get("summary", "Social media audit complete")

        report_url = await upload_report(
            slug=slug,
            report_type="social-audit",
            html_content=build_social_audit_report(payload, identity),
            identity=identity,
            summary=summary,
        )

        _fire_and_forget_persistence(
            slug, identity, "social_media_auditor", AgentVersions.SOCIAL_MEDIA_AUDITOR,
            report_url, payload, summary, firebase_user,
        )

        result = {**payload}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[Social Audit API Error]: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
