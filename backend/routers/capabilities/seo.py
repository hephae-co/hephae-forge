"""POST /api/capabilities/seo — SEO Deep Dive capability."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.seo_auditor import seo_auditor_agent
from backend.agents.seo_auditor.prompt import SEO_AUDITOR_INSTRUCTION
from backend.agents.seo_auditor.tools import pagespeed_tool
from backend.agents.shared_tools import google_search_tool
from backend.agents.marketing_swarm import generate_and_draft_marketing_content
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_seo_report
from backend.lib.db import write_agent_result, enrich_identity
from backend.config import AgentModels, AgentVersions
from backend.lib.adk_helpers import user_msg

logger = logging.getLogger(__name__)

router = APIRouter()


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
    return any(s.get("score", 0) > 0 for s in sections)


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


@router.post("/capabilities/seo")
async def capabilities_seo(request: Request):
    try:
        body = await request.json()
        identity = enrich_identity(body.get("identity", {}))

        if not identity.get("officialUrl"):
            return JSONResponse({"error": "No URL available for SEO Audit."}, status_code=400)

        logger.info(f"[SEO API] Launching SeoAuditorAgent for {identity['officialUrl']}...")

        # Primary run with gemini-2.5-pro
        report_data = await _run_seo_agent(seo_auditor_agent, identity)

        # Fallback: if primary model returned empty/useless sections, retry with lite model
        if not _has_valid_sections(report_data):
            logger.warning(
                f"[SEO API] Primary model returned empty sections for {identity['officialUrl']}. "
                f"Retrying with fallback model {AgentModels.FALLBACK_LITE_MODEL}..."
            )
            fallback_agent = LlmAgent(
                name="seoAuditorFallback",
                description="SEO Auditor (fallback lite model)",
                instruction=SEO_AUDITOR_INSTRUCTION,
                model=AgentModels.FALLBACK_LITE_MODEL,
                tools=[google_search_tool, pagespeed_tool],
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
                section["isAnalyzed"] = True
                if not isinstance(section.get("recommendations"), list):
                    section["recommendations"] = []

        final_report = {
            **report_data,
            "url": identity["officialUrl"],
            "sections": report_data.get("sections") if isinstance(report_data.get("sections"), list) else [],
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
