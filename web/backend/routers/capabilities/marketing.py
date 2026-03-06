"""POST /api/capabilities/marketing — Social Media Audit capability.

Runs 2-stage pipeline: SocialResearcher → SocialStrategist.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_request

from backend.agents.social_media_auditor import (
    social_researcher_agent,
    social_strategist_agent,
)
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_social_audit_report
from backend.lib.db import write_agent_result
from backend.lib.business_context import build_business_context
from backend.config import AgentVersions
from backend.lib.adk_helpers import user_msg
from backend.types import SocialAuditReport as SocialAuditReportModel

logger = logging.getLogger(__name__)

router = APIRouter()


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

        # ── Step 1: Social Researcher ──────────────────────────────────────
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

        # ── Step 2: Social Strategist ──────────────────────────────────────
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

        # ── Parse JSON ─────────────────────────────────────────────────────
        clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
        fb = clean_json_str.find("{")
        lb = clean_json_str.rfind("}")
        if fb != -1 and lb > fb:
            clean_json_str = clean_json_str[fb : lb + 1]
        payload = json.loads(clean_json_str)

        logger.info(f"[Social Audit API] Success: score={payload.get('overall_score')}, platforms={len(payload.get('platforms', []))}")

        # ── Upload report + write result ───────────────────────────────────
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
