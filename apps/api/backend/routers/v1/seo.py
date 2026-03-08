"""POST /api/v1/seo — V1 SEO Deep Dive (no report storage, returns raw data)."""

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

from backend.lib.auth import verify_api_key

from hephae_capabilities.seo_auditor import seo_auditor_agent
from hephae_capabilities.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_common.adk_helpers import user_msg
from backend.types import SeoReport, V1Response

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_final_response(event) -> bool:
    content = getattr(event, "content", None)
    if not content or not hasattr(content, "parts"):
        return False
    for part in content.parts:
        if hasattr(part, "function_call") and part.function_call:
            return False
        if hasattr(part, "function_response") and part.function_response:
            return False
    return True


@router.post("/v1/seo", response_model=V1Response[SeoReport], dependencies=[Depends(verify_api_key)])
async def v1_seo(request: Request):
    try:
        body = await request.json()
        identity = body.get("identity", {})

        if not identity or not identity.get("officialUrl"):
            return JSONResponse(
                {"error": "No target EnrichedProfile or URL available for SEO Audit."},
                status_code=400,
            )

        logger.info(f"[V1/SEO] Launching SeoAuditorAgent for {identity['officialUrl']}...")

        session_service = InMemorySessionService()
        runner = Runner(app_name="hephae-hub", agent=seo_auditor_agent, session_service=session_service)
        session_id = f"seo-v1-{int(time.time() * 1000)}"
        user_id = "api-v1-client"

        await session_service.create_session(
            app_name="hephae-hub", user_id=user_id, session_id=session_id, state={}
        )

        text_buffer = ""
        final_response_text = ""

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
                        continue
                    if getattr(part, "text", None):
                        text_buffer += part.text
                if _is_final_response(raw_event):
                    for part in content.parts:
                        if getattr(part, "text", None) and not getattr(part, "thought", False):
                            final_response_text += part.text

        output_text = final_response_text or text_buffer
        logger.info(
            f"[V1/SEO] Captured buffer={len(text_buffer)}, finalResponse={len(final_response_text)} chars"
        )

        report_data: dict = {}
        if output_text:
            raw = re.sub(r"```json\s*", "", output_text)
            raw = re.sub(r"```\s*", "", raw).strip()
            fb = raw.find("{")
            lb = raw.rfind("}")
            if fb != -1 and lb > fb:
                raw = raw[fb : lb + 1]
            try:
                report_data = json.loads(raw)
            except json.JSONDecodeError:
                try:
                    report_data = json.loads(re.sub(r",\s*([\]}])", r"\1", raw))
                except json.JSONDecodeError:
                    logger.error("[V1/SEO] All JSON parsing failed.")

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

        # Fire and forget marketing
        asyncio.create_task(
            generate_and_draft_marketing_content({"identity": identity, "seo": final_report}, "SEO Deep Audit")
        )

        return JSONResponse({"success": True, "data": final_report})

    except Exception as exc:
        logger.error(f"[V1/SEO Error]: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
