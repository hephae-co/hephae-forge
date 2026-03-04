"""POST /api/capabilities/marketing — Social Media Strategy capability."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.marketing_swarm import run_marketing_pipeline
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_marketing_report
from backend.lib.db import write_agent_result, enrich_identity
from backend.config import AgentVersions
from backend.types import MarketingReport as MarketingReportModel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/capabilities/marketing", response_model=MarketingReportModel)
async def capabilities_marketing(request: Request):
    try:
        body = await request.json()
        identity = enrich_identity(body.get("identity", {}))

        if not identity or not identity.get("name"):
            return JSONResponse(
                {"error": "Missing identity for Marketing Strategy"},
                status_code=400,
            )

        logger.info(f"[Marketing API] Running marketing pipeline for {identity['name']}...")

        result = await run_marketing_pipeline(identity)

        slug = generate_slug(identity["name"])

        report_url = await upload_report(
            slug=slug,
            report_type="marketing",
            html_content=build_marketing_report(result, identity),
            identity=identity,
            summary=result.get("summary", ""),
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity["name"],
                agent_name="marketing_swarm",
                agent_version=AgentVersions.MARKETING_SWARM,
                triggered_by="user",
                summary=result.get("summary", ""),
                report_url=report_url or None,
                raw_data=result,
            )
        )

        response = {**result}
        if report_url:
            response["reportUrl"] = report_url

        return JSONResponse(response)

    except Exception as exc:
        logger.error(f"[Marketing API Error]: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
