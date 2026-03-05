"""
Social post generator agents — Instagram + Facebook posts from report data.

Runs two agents in parallel to generate platform-specific social posts
highlighting key findings from business reports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from backend.config import AgentModels
from backend.lib.model_fallback import fallback_on_error
from backend.lib.adk_helpers import user_msg
from backend.agents.social_post_generator.prompts import (
    INSTAGRAM_POST_INSTRUCTION,
    FACEBOOK_POST_INSTRUCTION,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

instagram_post_agent = LlmAgent(
    name="InstagramPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=INSTAGRAM_POST_INSTRUCTION,
    output_key="instagramPost",
    on_model_error_callback=fallback_on_error,
)

facebook_post_agent = LlmAgent(
    name="FacebookPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=FACEBOOK_POST_INSTRUCTION,
    output_key="facebookPost",
    on_model_error_callback=fallback_on_error,
)

# ---------------------------------------------------------------------------
# Report type labels for context
# ---------------------------------------------------------------------------

REPORT_TYPE_LABELS = {
    "margin": "Margin Surgery",
    "traffic": "Foot Traffic Forecast",
    "seo": "SEO Deep Audit",
    "competitive": "Competitive Analysis",
    "marketing": "Social Media Insights",
    "profile": "Business Profile",
}


def _parse_json(raw: str) -> dict:
    """Extract JSON from agent output, stripping markdown fences."""
    if isinstance(raw, dict):
        return raw
    cleaned = re.sub(r"```json\n?|\n?```", "", str(raw)).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {}


def _build_context(
    business_name: str,
    report_type: str,
    summary: str,
    report_url: str,
    social_handles: dict[str, str] | None = None,
) -> str:
    """Build context string for the agents."""
    label = REPORT_TYPE_LABELS.get(report_type, report_type.replace("_", " ").title())
    parts = [
        f"Business: {business_name}",
        f"Report Type: {label}",
        f"Key Finding / Summary: {summary}",
        f"Report URL: {report_url}",
        f"Hephae Website: https://hephae.co",
    ]
    if social_handles:
        if social_handles.get("instagram"):
            parts.append(f"Instagram Handle: {social_handles['instagram']}")
        if social_handles.get("facebook"):
            parts.append(f"Facebook Page: {social_handles['facebook']}")
    return "\n".join(parts)


def _fallback_posts(
    business_name: str,
    report_type: str,
    summary: str,
    report_url: str,
) -> dict[str, Any]:
    """Template-based fallback if agent generation fails."""
    label = REPORT_TYPE_LABELS.get(report_type, report_type.title())
    return {
        "instagram": {
            "caption": (
                f"We just ran {label} on {business_name} and the results are eye-opening.\n\n"
                f"{summary}\n\n"
                f"Full report at hephae.co\n\n"
                f"#Hephae #BusinessIntelligence #AIAnalysis"
            )
        },
        "facebook": {
            "post": (
                f"Hephae Forge just completed a {label} for {business_name}.\n\n"
                f"{summary}\n\n"
                f"Read the full report: {report_url}\n\n"
                f"Get your own analysis at hephae.co"
            )
        },
    }


async def _run_agent(agent: LlmAgent, output_key: str, prompt: str) -> str:
    """Run a single agent and return its output."""
    session_service = InMemorySessionService()
    session_id = f"social-{output_key}-{int(time.time() * 1000)}"
    runner = Runner(
        app_name="hephae-hub",
        agent=agent,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys", state={}
    )
    async for _ in runner.run_async(
        session_id=session_id, user_id="sys", new_message=user_msg(prompt),
    ):
        pass

    session = await session_service.get_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys"
    )
    return (session.state or {}).get(output_key, "{}")


async def generate_social_posts(
    business_name: str,
    report_type: str,
    summary: str,
    report_url: str,
    social_handles: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate Instagram + Facebook posts in parallel.

    Returns:
        {
            "instagram": {"caption": "..."},
            "facebook": {"post": "..."},
        }
    """
    context = _build_context(business_name, report_type, summary, report_url, social_handles)
    logger.info(f"[SocialPostGen] Generating posts for {business_name} ({report_type})")

    try:
        ig_raw, fb_raw = await asyncio.gather(
            _run_agent(instagram_post_agent, "instagramPost", context),
            _run_agent(facebook_post_agent, "facebookPost", context),
        )

        ig_data = _parse_json(ig_raw)
        fb_data = _parse_json(fb_raw)

        result = {
            "instagram": {"caption": ig_data.get("caption", "")},
            "facebook": {"post": fb_data.get("post", "")},
        }

        # If either is empty, use fallback for that platform
        fallback = _fallback_posts(business_name, report_type, summary, report_url)
        if not result["instagram"]["caption"]:
            result["instagram"] = fallback["instagram"]
        if not result["facebook"]["post"]:
            result["facebook"] = fallback["facebook"]

        logger.info(
            f"[SocialPostGen] Done: ig={len(result['instagram']['caption'])}c, "
            f"fb={len(result['facebook']['post'])}c"
        )
        return result

    except Exception as e:
        logger.error(f"[SocialPostGen] Failed for {business_name}: {e}")
        return _fallback_posts(business_name, report_type, summary, report_url)
