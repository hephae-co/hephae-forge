"""POST /api/social-posts/generate — Generate social media posts from report data.

Supports two modes:
  1. Legacy: pass businessName + summary (existing frontend flow)
  2. Enriched: pass just businessName — auto-fetches latestOutputs from Firestore
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from hephae_agents.social.post_generator import generate_social_posts
from hephae_api.types import SocialPostsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/social-posts/generate",
    response_model=SocialPostsResponse,
    summary="Generate Instagram + Facebook + X posts from report data",
)
async def social_posts_generate(request: Request):
    try:
        body = await request.json()
        business_name = body.get("businessName", "")
        report_type = body.get("reportType", "")
        summary = body.get("summary", "")
        report_url = body.get("reportUrl", "")
        social_handles = body.get("socialHandles")

        if not business_name:
            return JSONResponse(
                {"error": "businessName is required"},
                status_code=400,
            )

        # Data-enriched mode: fetch from Firestore when no summary provided
        latest_outputs = None
        if not summary:
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            data = fetch_latest_outputs(business_name)
            latest_outputs = data.get("outputs")

            if not latest_outputs:
                return JSONResponse(
                    {"error": "No analysis data found. Run at least one analysis first, or provide a summary."},
                    status_code=404,
                )

            # Auto-populate social handles from stored socialLinks if not provided
            if not social_handles:
                stored_links = data.get("socialLinks", {})
                if stored_links:
                    social_handles = {
                        k: v for k, v in stored_links.items()
                        if k in ("instagram", "facebook", "twitter") and v
                    } or None

        # Legacy mode validation
        if not latest_outputs and not summary:
            return JSONResponse(
                {"error": "businessName and summary are required"},
                status_code=400,
            )

        # Build cdn_report_urls from client-provided reportUrls or latestOutputs
        cdn_report_urls = body.get("reportUrls") or {}
        if not cdn_report_urls and latest_outputs:
            # Extract reportUrls from latestOutputs
            agent_to_type = {
                "margin_surgeon": "margin",
                "seo_auditor": "seo",
                "traffic_forecaster": "traffic",
                "competitive_analyzer": "competitive",
                "marketing_swarm": "marketing",
            }
            for agent_key, rtype in agent_to_type.items():
                agent_data = latest_outputs.get(agent_key)
                if isinstance(agent_data, dict) and agent_data.get("reportUrl"):
                    cdn_report_urls[rtype] = agent_data["reportUrl"]

        # Single reportUrl also goes into the dict
        if report_url and report_type and report_type not in cdn_report_urls:
            cdn_report_urls[report_type] = report_url

        result = await generate_social_posts(
            business_name=business_name,
            report_type=report_type,
            summary=summary,
            report_url=report_url,
            social_handles=social_handles,
            latest_outputs=latest_outputs,
            cdn_report_urls=cdn_report_urls or None,
        )

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Social post generation failed: {e}")
        return JSONResponse(
            {"error": "Social post generation failed"},
            status_code=500,
        )
