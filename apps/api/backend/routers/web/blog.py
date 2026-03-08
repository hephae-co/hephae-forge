"""POST /api/blog/generate — Generate a full blog post from stored analysis data."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from hephae_capabilities.social.blog_writer import generate_blog_post
from hephae_db.context.latest_outputs import fetch_latest_outputs
from hephae_common.report_storage import generate_slug, upload_report
from hephae_common.report_templates import build_blog_report
from hephae_common.social_card import generate_universal_social_card
from hephae_db.firestore.agent_results import write_agent_result
from backend.config import AgentVersions, StorageConfig
from backend.types import BlogPostResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _pick_hero_stats(
    latest_outputs: dict, business_name: str
) -> tuple[str, str]:
    """Pick the most impressive stat for the hero image card."""
    m = latest_outputs.get("margin_surgeon")
    if m and isinstance(m, dict):
        leak = m.get("totalLeakage")
        if leak is not None:
            try:
                return f"${float(leak):,.0f}/mo", "Profit Leakage Exposed"
            except (ValueError, TypeError):
                pass
        score = m.get("score")
        if score is not None:
            return f"{score}/100", "Margin Surgery Score"

    s = latest_outputs.get("seo_auditor")
    if s and isinstance(s, dict):
        score = s.get("score")
        if score is not None:
            return f"{score}/100", "SEO Audit Score"

    c = latest_outputs.get("competitive_analyzer")
    if c and isinstance(c, dict):
        count = c.get("competitor_count")
        if count is not None:
            return f"{count}", "Competitors Analyzed"

    return "Deep Dive", f"Hephae Analysis: {business_name}"


async def _upload_hero_image(slug: str, image_bytes: bytes) -> str:
    """Upload hero image PNG to GCS, return public URL."""
    ts = int(time.time() * 1000)
    object_path = f"{slug}/blog-hero-{ts}.png"
    public_url = f"{StorageConfig.BASE_URL}/{object_path}"

    try:
        from hephae_common.firebase import get_bucket

        blob = get_bucket().blob(object_path)
        blob.upload_from_string(image_bytes, content_type="image/png")
        blob.cache_control = "public, max-age=86400"
        blob.patch()
        logger.info(f"[Blog] Uploaded hero image -> {public_url}")
        return public_url
    except Exception as e:
        logger.warning(f"[Blog] Failed to upload hero image for {slug}: {e}")
        return ""


@router.post("/blog/generate", response_model=BlogPostResponse)
async def blog_generate(request: Request):
    try:
        body = await request.json()
        business_name = body.get("businessName", "")

        if not business_name:
            return JSONResponse(
                {"error": "businessName is required"}, status_code=400
            )

        # Fetch all latestOutputs from Firestore
        data = fetch_latest_outputs(business_name)
        latest_outputs = data.get("outputs", {})

        if not latest_outputs:
            return JSONResponse(
                {
                    "error": f"No analysis data found for '{business_name}'. "
                    "Run at least one analysis first."
                },
                status_code=404,
            )

        slug = generate_slug(business_name)

        # Run blog generation and hero image generation in parallel
        headline, subtitle = _pick_hero_stats(latest_outputs, business_name)
        blog_task = generate_blog_post(business_name, latest_outputs)
        hero_task = generate_universal_social_card(
            business_name=business_name,
            report_type="profile",
            headline=headline,
            subtitle=subtitle,
            highlight="Hephae Blog",
        )

        blog_result, hero_bytes = await asyncio.gather(blog_task, hero_task)

        # Upload hero image
        hero_url = await _upload_hero_image(slug, hero_bytes)

        # Fetch identity for template branding
        from hephae_db.firestore.businesses import read_business

        stored = read_business(slug) or {}

        # Build full HTML blog page
        html_content = build_blog_report(
            article_html=blog_result["html_content"],
            business_name=business_name,
            title=blog_result["title"],
            hero_image_url=hero_url,
            primary_color=stored.get("primaryColor", ""),
            logo_url=stored.get("logoUrl", ""),
            favicon_url=stored.get("favicon", ""),
        )

        # Upload to GCS
        report_url = await upload_report(
            slug=slug,
            report_type="blog",
            html_content=html_content,
        )

        # Write to Firestore (non-blocking)
        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=business_name,
                agent_name="blog_writer",
                agent_version=AgentVersions.BLOG_WRITER,
                triggered_by="user",
                summary=blog_result["title"],
                report_url=report_url or None,
                raw_data={
                    "title": blog_result["title"],
                    "word_count": blog_result["word_count"],
                    "data_sources": blog_result["data_sources"],
                },
            )
        )

        return JSONResponse(
            {
                "title": blog_result["title"],
                "htmlContent": blog_result["html_content"],
                "reportUrl": report_url,
                "heroImageUrl": hero_url,
                "wordCount": blog_result["word_count"],
                "dataSources": blog_result["data_sources"],
            }
        )

    except Exception as e:
        logger.error(f"[Blog API] Generation failed: {e}")
        return JSONResponse(
            {"error": "Blog generation failed"}, status_code=500
        )
