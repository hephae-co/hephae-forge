"""POST /api/social-posts/generate — Generate social media posts from report data."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.social_post_generator import generate_social_posts
from backend.types import SocialPostsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/social-posts/generate",
    response_model=SocialPostsResponse,
    summary="Generate Instagram + Facebook posts from report data",
)
async def social_posts_generate(request: Request):
    try:
        body = await request.json()
        business_name = body.get("businessName", "")
        report_type = body.get("reportType", "")
        summary = body.get("summary", "")
        report_url = body.get("reportUrl", "")
        social_handles = body.get("socialHandles")

        if not business_name or not summary:
            return JSONResponse(
                {"error": "businessName and summary are required"},
                status_code=400,
            )

        result = await generate_social_posts(
            business_name=business_name,
            report_type=report_type,
            summary=summary,
            report_url=report_url,
            social_handles=social_handles,
        )

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Social post generation failed: {e}")
        return JSONResponse(
            {"error": "Social post generation failed"},
            status_code=500,
        )
