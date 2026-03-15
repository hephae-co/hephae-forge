"""POST /api/social-card — Generate PNG social card."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response, JSONResponse

from hephae_common.social_card import generate_universal_social_card

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/social-card")
async def social_card(request: Request):
    try:
        body = await request.json()
        business_name = body.get("businessName", "")

        if not business_name:
            return JSONResponse({"error": "Missing businessName"}, status_code=400)

        # Universal params
        report_type = body.get("reportType", "profile")
        headline = body.get("headline", "")
        subtitle = body.get("subtitle", "")
        highlight = body.get("highlight", "")

        # Backward compat: old margin-specific params
        if not headline and body.get("totalLeakage"):
            total_leakage = body["totalLeakage"]
            headline = f"${total_leakage:,.0f}" if isinstance(total_leakage, (int, float)) else str(total_leakage)
            subtitle = subtitle or "Potential Annual Profit Recovered"
            report_type = "margin"
        if not highlight and body.get("topItem"):
            highlight = f"Top Fix: {body['topItem']}"

        image_bytes = await generate_universal_social_card(
            business_name=business_name,
            report_type=report_type,
            headline=headline,
            subtitle=subtitle,
            highlight=highlight,
        )

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="Hephae-Report.png"'},
        )

    except Exception as e:
        logger.error(f"Social Card Generation Failed: {e}")
        return JSONResponse({"error": "Generation Failed"}, status_code=500)
