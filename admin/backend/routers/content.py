"""Content generation and publishing endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query

from backend.lib.forge_auth import forge_api_key_headers
from pydantic import BaseModel

from backend.config import settings
from backend.lib.db.content_posts import (
    save_content_post,
    get_content_post,
    list_content_posts,
    update_content_post,
    delete_content_post,
)
from backend.lib.db.zipcode_research import get_run
from backend.lib.db.area_research import load_area_research
from backend.lib.db.combined_context import get_combined_context
from backend.lib.social_client import get_client
from backend.types import (
    ContentPost,
    ContentType,
    ContentPlatform,
    ContentStatus,
    ContentSourceType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/content", tags=["content"])

# Character limits per platform
PLATFORM_LIMITS = {
    ContentPlatform.X: 280,
    ContentPlatform.INSTAGRAM: 2200,
    ContentPlatform.FACEBOOK: 63206,
    ContentPlatform.BLOG: None,
}


class GenerateRequest(BaseModel):
    platform: ContentPlatform
    sourceType: ContentSourceType
    sourceId: str


class UpdateRequest(BaseModel):
    content: str | None = None
    title: str | None = None
    hashtags: list[str] | None = None


async def _fetch_research_data(source_type: ContentSourceType, source_id: str) -> tuple[dict, str]:
    """Fetch research data and return (data_dict, label)."""
    if source_type == ContentSourceType.ZIPCODE_RESEARCH:
        run = await get_run(source_id)
        if not run:
            raise HTTPException(status_code=404, detail="Zip code research not found")
        return run.report.model_dump(mode="json"), f"Zip {run.zipCode}"

    if source_type == ContentSourceType.AREA_RESEARCH:
        area = await load_area_research(source_id)
        if not area:
            raise HTTPException(status_code=404, detail="Area research not found")
        data = {}
        if area.summary:
            data["summary"] = area.summary.model_dump(mode="json")
        data["area"] = area.area
        data["businessType"] = area.businessType
        data["zipCodes"] = area.zipCodes
        return data, f"{area.area} ({area.businessType})"

    if source_type == ContentSourceType.COMBINED_CONTEXT:
        ctx = await get_combined_context(source_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="Combined context not found")
        return ctx.context.model_dump(mode="json"), f"Combined: {', '.join(ctx.sourceZipCodes)}"

    raise HTTPException(status_code=400, detail="Invalid source type")


@router.post("/generate")
async def generate_content(req: GenerateRequest):
    """Fetch research data, call forge to generate content, save as draft."""
    research_data, label = await _fetch_research_data(req.sourceType, req.sourceId)

    content_type = ContentType.BLOG if req.platform == ContentPlatform.BLOG else ContentType.SOCIAL
    max_length = PLATFORM_LIMITS.get(req.platform)

    constraints: dict = {"includeHashtags": True}
    if max_length:
        constraints["maxLength"] = max_length

    forge_payload = {
        "platform": req.platform.value,
        "contentType": content_type.value,
        "researchData": research_data,
        "constraints": constraints,
    }

    # Call hephae-forge
    forge_url = f"{settings.FORGE_URL}/api/v1/generate-content"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(forge_url, json=forge_payload, headers=forge_api_key_headers())
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Forge returned {resp.status_code}: {resp.text[:500]}")
        forge_result = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Forge service unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Forge request timed out")

    if not forge_result.get("success"):
        raise HTTPException(status_code=502, detail=forge_result.get("error", "Forge generation failed"))

    data = forge_result.get("data", {})

    post = ContentPost(
        type=content_type,
        platform=req.platform,
        status=ContentStatus.DRAFT,
        sourceType=req.sourceType,
        sourceId=req.sourceId,
        sourceLabel=label,
        content=data.get("content", ""),
        title=data.get("title"),
        hashtags=data.get("hashtags", []),
    )

    post_id = await save_content_post(post)
    post.id = post_id
    return {"success": True, "post": post.model_dump(mode="json")}


@router.get("")
async def list_posts(
    platform: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    posts = await list_content_posts(limit=limit, platform=platform)
    return [p.model_dump(mode="json") for p in posts]


@router.get("/{post_id}")
async def get_post(post_id: str):
    post = await get_content_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post.model_dump(mode="json")


@router.patch("/{post_id}")
async def edit_post(post_id: str, req: UpdateRequest):
    post = await get_content_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != ContentStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only drafts can be edited")

    updates = {}
    if req.content is not None:
        updates["content"] = req.content
    if req.title is not None:
        updates["title"] = req.title
    if req.hashtags is not None:
        updates["hashtags"] = req.hashtags

    if updates:
        await update_content_post(post_id, updates)

    updated = await get_content_post(post_id)
    return updated.model_dump(mode="json")


@router.post("/{post_id}/publish")
async def publish_post(post_id: str):
    post = await get_content_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == ContentStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Already published")

    now = datetime.utcnow()

    # Blog: just mark as published
    if post.platform == ContentPlatform.BLOG:
        await update_content_post(post_id, {
            "status": ContentStatus.PUBLISHED.value,
            "publishedAt": now,
        })
        updated = await get_content_post(post_id)
        return {"success": True, "post": updated.model_dump(mode="json")}

    # Social: post via platform API
    text = post.content
    if post.hashtags:
        tag_str = " ".join(f"#{h.lstrip('#')}" for h in post.hashtags)
        text = f"{text}\n\n{tag_str}"

    try:
        client = get_client(post.platform.value)
    except ValueError as e:
        await update_content_post(post_id, {
            "status": ContentStatus.FAILED.value,
            "error": str(e),
        })
        raise HTTPException(status_code=400, detail=str(e))

    result = await client.post(text)

    if result.success:
        await update_content_post(post_id, {
            "status": ContentStatus.PUBLISHED.value,
            "publishedAt": now,
            "platformPostId": result.post_id,
        })
    else:
        await update_content_post(post_id, {
            "status": ContentStatus.FAILED.value,
            "error": result.error,
        })

    updated = await get_content_post(post_id)
    return {"success": result.success, "post": updated.model_dump(mode="json"), "error": result.error}


@router.delete("/{post_id}")
async def remove_post(post_id: str):
    post = await get_content_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == ContentStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Cannot delete published posts")
    await delete_content_post(post_id)
    return {"success": True}
