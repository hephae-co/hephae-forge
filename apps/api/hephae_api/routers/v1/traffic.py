"""POST /api/v1/traffic — V1 Foot Traffic Forecast (no report storage)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_api_key

from hephae_agents.traffic_forecaster import ForecasterAgent
from hephae_agents.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_api.types import ForecastResponse, V1Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/traffic", response_model=V1Response[ForecastResponse], dependencies=[Depends(verify_api_key)])
async def v1_traffic(request: Request):
    try:
        body = await request.json()
        identity = body.get("identity", {})

        if not identity or not identity.get("name"):
            return JSONResponse(
                {"error": "Missing Target EnrichedProfile (identity) for Traffic Forecaster"},
                status_code=400,
            )

        logger.info(f"[V1/Traffic] Triggering Foot Traffic Capability for {identity['name']}...")
        forecast_data = await ForecasterAgent.forecast(identity)

        # Fire and forget marketing
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "forecast": forecast_data}, "Foot Traffic Heatmap"
            )
        )

        return JSONResponse({"success": True, "data": forecast_data})

    except Exception as exc:
        logger.error(f"[V1/Traffic] Failed: {exc}")
        return JSONResponse({"error": str(exc) or "Internal Server Error"}, status_code=500)
