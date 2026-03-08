"""
Social post generator agents — Instagram + Facebook + X/Twitter posts from report data.

Runs three agents in parallel to generate platform-specific social posts
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

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from hephae_capabilities.social.post_generator.prompts import (
    INSTAGRAM_POST_INSTRUCTION,
    FACEBOOK_POST_INSTRUCTION,
    TWITTER_POST_INSTRUCTION,
    EMAIL_OUTREACH_INSTRUCTION,
    CONTACT_FORM_INSTRUCTION,
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

twitter_post_agent = LlmAgent(
    name="TwitterPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=TWITTER_POST_INSTRUCTION,
    output_key="twitterPost",
    on_model_error_callback=fallback_on_error,
)

email_outreach_agent = LlmAgent(
    name="EmailOutreachAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=EMAIL_OUTREACH_INSTRUCTION,
    output_key="emailOutreach",
    on_model_error_callback=fallback_on_error,
)

contact_form_agent = LlmAgent(
    name="ContactFormAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=CONTACT_FORM_INSTRUCTION,
    output_key="contactFormDraft",
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
    """Build context string for the agents (legacy mode — single summary)."""
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
        if social_handles.get("twitter"):
            parts.append(f"Twitter/X Handle: {social_handles['twitter']}")
    return "\n".join(parts)


def _build_rich_context(
    business_name: str,
    latest_outputs: dict[str, Any],
    report_type: str = "",
    social_handles: dict[str, str] | None = None,
) -> str:
    """Build rich context from stored Firestore latestOutputs for the agents."""
    parts = [
        f"Business: {business_name}",
        f"Hephae Website: https://hephae.co",
    ]

    if social_handles:
        if social_handles.get("instagram"):
            parts.append(f"Instagram Handle: {social_handles['instagram']}")
        if social_handles.get("facebook"):
            parts.append(f"Facebook Page: {social_handles['facebook']}")
        if social_handles.get("twitter"):
            parts.append(f"Twitter/X Handle: {social_handles['twitter']}")

    # --- Per-agent data sections ---

    m = latest_outputs.get("margin_surgeon")
    if m and isinstance(m, dict):
        parts.append("\n## Margin Surgery Results")
        if m.get("score") is not None:
            parts.append(f"Score: {m['score']}/100")
        if m.get("totalLeakage") is not None:
            try:
                parts.append(f"Total Profit Leakage: ${float(m['totalLeakage']):,.0f}/mo")
            except (ValueError, TypeError):
                parts.append(f"Total Profit Leakage: {m['totalLeakage']}")
        if m.get("menu_item_count"):
            parts.append(f"Menu Items Analyzed: {m['menu_item_count']}")
        if m.get("summary"):
            parts.append(f"Summary: {m['summary']}")
        if m.get("reportUrl"):
            parts.append(f"Full Report: {m['reportUrl']}")

    s = latest_outputs.get("seo_auditor")
    if s and isinstance(s, dict):
        parts.append("\n## SEO Audit Results")
        if s.get("score") is not None:
            parts.append(f"Overall Score: {s['score']}/100")
        for key, label in [
            ("seo_technical_score", "Technical"),
            ("seo_content_score", "Content"),
            ("seo_ux_score", "UX"),
            ("seo_performance_score", "Performance"),
            ("seo_authority_score", "Authority"),
        ]:
            if s.get(key) is not None:
                parts.append(f"  - {label}: {s[key]}/100")
        if s.get("summary"):
            parts.append(f"Summary: {s['summary']}")
        if s.get("reportUrl"):
            parts.append(f"Full Report: {s['reportUrl']}")

    t = latest_outputs.get("traffic_forecaster")
    if t and isinstance(t, dict):
        parts.append("\n## Traffic Forecast Results")
        if t.get("peak_slot_score") is not None:
            parts.append(f"Peak Traffic Score: {t['peak_slot_score']}")
        if t.get("summary"):
            parts.append(f"Summary: {t['summary']}")
        if t.get("reportUrl"):
            parts.append(f"Full Report: {t['reportUrl']}")

    c = latest_outputs.get("competitive_analyzer")
    if c and isinstance(c, dict):
        parts.append("\n## Competitive Analysis Results")
        if c.get("competitor_count") is not None:
            parts.append(f"Competitors Analyzed: {c['competitor_count']}")
        if c.get("avg_threat_level") is not None:
            parts.append(f"Avg Threat Level: {c['avg_threat_level']}/10")
        if c.get("summary"):
            parts.append(f"Summary: {c['summary']}")
        if c.get("reportUrl"):
            parts.append(f"Full Report: {c['reportUrl']}")

    mk = latest_outputs.get("marketing_swarm")
    if mk and isinstance(mk, dict):
        parts.append("\n## Marketing Insights")
        if mk.get("summary"):
            parts.append(f"Summary: {mk['summary']}")
        if mk.get("reportUrl"):
            parts.append(f"Full Report: {mk['reportUrl']}")

    # Focus instruction
    if report_type:
        label = REPORT_TYPE_LABELS.get(report_type, report_type.replace("_", " ").title())
        parts.append(f"\nFOCUS: This post should primarily highlight the {label} findings.")

    return "\n".join(parts)


def _fallback_posts(
    business_name: str,
    report_type: str,
    summary: str,
    report_url: str,
) -> dict[str, Any]:
    """Template-based fallback if agent generation fails."""
    label = REPORT_TYPE_LABELS.get(report_type, report_type.title())
    short_summary = summary[:100] + "..." if len(summary) > 100 else summary
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
                f"Hephae just completed a {label} for {business_name}.\n\n"
                f"{summary}\n\n"
                f"Read the full report: {report_url}\n\n"
                f"Get your own analysis at hephae.co"
            )
        },
        "twitter": {
            "tweet": (
                f"{business_name}: {short_summary} "
                f"See the full {label} breakdown. "
                f"#Hephae"
            )[:280]
        },
        "email": {
            "subject": f"Insights from {business_name}'s {label}",
            "body": (
                f"Hi,\n\n"
                f"We've completed a {label} for {business_name} and found some interesting insights.\n\n"
                f"{summary}\n\n"
                f"Learn more at hephae.co\n\n"
                f"Best regards,\nThe Hephae Team"
            ),
        },
        "contactForm": {
            "message": (
                f"Hi, Hephae here. We ran a {label} on your business and found that {short_summary}. "
                f"We help businesses like yours optimize with AI-powered insights. "
                f"Check us out at hephae.co"
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
    report_type: str = "",
    summary: str = "",
    report_url: str = "",
    social_handles: dict[str, str] | None = None,
    latest_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate Instagram + Facebook + X/Twitter + Email + Contact Form content in parallel.

    Args:
        latest_outputs: When provided, builds rich context from stored Firestore
            data instead of using the single summary string (data-enriched mode).

    Returns:
        {
            "instagram": {"caption": "..."},
            "facebook": {"post": "..."},
            "twitter": {"tweet": "..."},
            "email": {"subject": "...", "body": "..."},
            "contactForm": {"message": "..."},
        }
    """
    if latest_outputs:
        context = _build_rich_context(business_name, latest_outputs, report_type, social_handles)
    else:
        context = _build_context(business_name, report_type, summary, report_url, social_handles)
    logger.info(f"[SocialPostGen] Generating 5-channel content for {business_name} ({report_type})")

    try:
        ig_raw, fb_raw, tw_raw, email_raw, contact_raw = await asyncio.gather(
            _run_agent(instagram_post_agent, "instagramPost", context),
            _run_agent(facebook_post_agent, "facebookPost", context),
            _run_agent(twitter_post_agent, "twitterPost", context),
            _run_agent(email_outreach_agent, "emailOutreach", context),
            _run_agent(contact_form_agent, "contactFormDraft", context),
        )

        ig_data = _parse_json(ig_raw)
        fb_data = _parse_json(fb_raw)
        tw_data = _parse_json(tw_raw)
        email_data = _parse_json(email_raw)
        contact_data = _parse_json(contact_raw)

        result = {
            "instagram": {"caption": ig_data.get("caption", "")},
            "facebook": {"post": fb_data.get("post", "")},
            "twitter": {"tweet": tw_data.get("tweet", "")},
            "email": {
                "subject": email_data.get("subject", ""),
                "body": email_data.get("body", ""),
            },
            "contactForm": {"message": contact_data.get("message", "")},
        }

        # If any channel is empty, use fallback for that channel
        fallback = _fallback_posts(business_name, report_type, summary, report_url)
        if not result["instagram"]["caption"]:
            result["instagram"] = fallback["instagram"]
        if not result["facebook"]["post"]:
            result["facebook"] = fallback["facebook"]
        if not result["twitter"]["tweet"]:
            result["twitter"] = fallback["twitter"]
        if not result["email"]["body"]:
            result["email"] = fallback["email"]
        if not result["contactForm"]["message"]:
            result["contactForm"] = fallback["contactForm"]

        logger.info(
            f"[SocialPostGen] Done: ig={len(result['instagram']['caption'])}c, "
            f"fb={len(result['facebook']['post'])}c, "
            f"tw={len(result['twitter']['tweet'])}c, "
            f"email_subject={len(result['email']['subject'])}c, "
            f"contact={len(result['contactForm']['message'])}c"
        )
        return result

    except Exception as e:
        logger.error(f"[SocialPostGen] Failed for {business_name}: {e}")
        return _fallback_posts(business_name, report_type, summary, report_url)
