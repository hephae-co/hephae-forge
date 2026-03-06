"""POST /api/capabilities/traffic — Foot Traffic Forecast capability."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_request

from backend.agents.traffic_forecaster import ForecasterAgent
from backend.agents.marketing_swarm import generate_and_draft_marketing_content
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_traffic_report
from backend.lib.db import write_agent_result
from backend.lib.business_context import build_business_context
from backend.config import AgentVersions
from backend.types import ForecastResponse as ForecastResponseModel

logger = logging.getLogger(__name__)

router = APIRouter()


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
