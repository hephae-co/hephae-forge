"""POST /api/overview — Lightweight business overview (Google Search + Maps Grounding)."""

from __future__ import annotations

import logging
import traceback

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/overview", dependencies=[Depends(verify_request)])
async def overview(request: Request):
    """Generate a lightweight business overview using Google Search + Maps Grounding.

    Replaces the heavy discovery pipeline for the initial chat experience.
    No authentication required beyond HMAC request signing.
    """
    try:
        body = await request.json()
        identity = body.get("identity")

        if not identity or not identity.get("name"):
            return JSONResponse({"error": "Missing identity (name required)"}, status_code=400)

        name = identity.get("name", "Unknown")
        logger.info(f"[API/Overview] Generating overview for: {name}")

        from hephae_agents.business_overview.runner import run_business_overview

        light = body.get("light", False)
        result = await run_business_overview(identity, light=light)

        logger.info(f"[API/Overview] Overview complete for: {name}")
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"[API/Overview] Failed: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
