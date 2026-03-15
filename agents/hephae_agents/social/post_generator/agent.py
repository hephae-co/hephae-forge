"""
Social post generator agents — 5-channel parallel generation via ParallelAgent.

Generates Instagram + Facebook + X/Twitter + Email + Contact Form content
from report data using ADK ParallelAgent orchestration.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_db.schemas.agent_outputs import (
    InstagramPostOutput,
    FacebookPostOutput,
    TwitterPostOutput,
    EmailOutreachOutput,
    ContactFormOutput,
)
from hephae_agents.social.post_generator.prompts import (
    INSTAGRAM_POST_INSTRUCTION,
    FACEBOOK_POST_INSTRUCTION,
    TWITTER_POST_INSTRUCTION,
    EMAIL_OUTREACH_INSTRUCTION,
    CONTACT_FORM_INSTRUCTION,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent definitions — all use output_key for session state storage
# ---------------------------------------------------------------------------

instagram_post_agent = LlmAgent(
    name="InstagramPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=INSTAGRAM_POST_INSTRUCTION,
    output_key="instagramPost",
    output_schema=InstagramPostOutput,
    on_model_error_callback=fallback_on_error,
)

facebook_post_agent = LlmAgent(
    name="FacebookPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=FACEBOOK_POST_INSTRUCTION,
    output_key="facebookPost",
    output_schema=FacebookPostOutput,
    on_model_error_callback=fallback_on_error,
)

twitter_post_agent = LlmAgent(
    name="TwitterPostAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=TWITTER_POST_INSTRUCTION,
    output_key="twitterPost",
    output_schema=TwitterPostOutput,
    on_model_error_callback=fallback_on_error,
)

email_outreach_agent = LlmAgent(
    name="EmailOutreachAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=EMAIL_OUTREACH_INSTRUCTION,
    output_key="emailOutreach",
    output_schema=EmailOutreachOutput,
    on_model_error_callback=fallback_on_error,
)

contact_form_agent = LlmAgent(
    name="ContactFormAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=CONTACT_FORM_INSTRUCTION,
    output_key="contactFormDraft",
    output_schema=ContactFormOutput,
    on_model_error_callback=fallback_on_error,
)

# ---------------------------------------------------------------------------
# ParallelAgent orchestrator — runs all 5 channel agents concurrently
# ---------------------------------------------------------------------------

social_post_parallel = ParallelAgent(
    name="SocialPostParallel",
    description="Generate content for 5 outreach channels in parallel: Instagram, Facebook, Twitter, Email, Contact Form.",
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
    sub_agents=[
        instagram_post_agent,
        facebook_post_agent,
        twitter_post_agent,
        email_outreach_agent,
        contact_form_agent,
    ],
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
    cdn_report_urls: dict[str, str] | None = None,
) -> str:
    """Build context string for the agents (legacy mode — single summary)."""
    label = REPORT_TYPE_LABELS.get(report_type, report_type.replace("_", " ").title())
    parts = [
        f"Business: {business_name}",
        f"Report Type: {label}",
        f"Key Finding / Summary: {summary}",
        f"Hephae Website: https://hephae.co",
    ]
    if social_handles:
        if social_handles.get("instagram"):
            parts.append(f"Instagram Handle: {social_handles['instagram']}")
        if social_handles.get("facebook"):
            parts.append(f"Facebook Page: {social_handles['facebook']}")
        if social_handles.get("twitter"):
            parts.append(f"Twitter/X Handle: {social_handles['twitter']}")

    all_urls = cdn_report_urls or {}
    if report_url and report_type and report_type not in all_urls:
        all_urls[report_type] = report_url
    if all_urls:
        parts.append("\n## REPORT LINKS (MUST include at least one in your output)")
        for rtype, url in all_urls.items():
            rlabel = REPORT_TYPE_LABELS.get(rtype, rtype.replace("_", " ").title())
            parts.append(f"- {rlabel}: {url}")
    elif report_url:
        parts.append(f"\n## REPORT LINKS (MUST include in your output)\n- {label}: {report_url}")

    return "\n".join(parts)


def _build_rich_context(
    business_name: str,
    latest_outputs: dict[str, Any],
    report_type: str = "",
    social_handles: dict[str, str] | None = None,
    cdn_report_urls: dict[str, str] | None = None,
    cdn_card_urls: dict[str, str] | None = None,
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

    report_urls = cdn_report_urls or {}
    if report_urls:
        parts.append("\n## REPORT LINKS (MUST include at least one in your output)")
        for rtype, url in report_urls.items():
            label = REPORT_TYPE_LABELS.get(rtype, rtype.replace("_", " ").title())
            parts.append(f"- {label}: {url}")

    card_urls = cdn_card_urls or {}
    if card_urls:
        parts.append("\n## SOCIAL CARD IMAGES (use these as post images)")
        for rtype, url in card_urls.items():
            label = REPORT_TYPE_LABELS.get(rtype, rtype.replace("_", " ").title())
            parts.append(f"- {label} Card: {url}")

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
                f"Hi {business_name}, Hephae here. We ran a {label} on your business and found that {short_summary}. "
                f"We help businesses like yours optimize with AI-powered insights. "
                f"Check us out at hephae.co"
            )
        },
    }


async def generate_social_posts(
    business_name: str,
    report_type: str = "",
    summary: str = "",
    report_url: str = "",
    social_handles: dict[str, str] | None = None,
    latest_outputs: dict[str, Any] | None = None,
    cdn_report_urls: dict[str, str] | None = None,
    cdn_card_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate 5-channel content via ParallelAgent orchestration.

    Returns:
        {
            "instagram": {"caption": "...", "reportLink": "...", "imageUrl": "..."},
            "facebook": {"post": "...", "reportLink": "...", "imageUrl": "..."},
            "twitter": {"tweet": "...", "reportLink": "...", "imageUrl": "..."},
            "email": {"subject": "...", "body": "..."},
            "contactForm": {"message": "..."},
        }
    """
    if latest_outputs:
        context = _build_rich_context(
            business_name, latest_outputs, report_type, social_handles,
            cdn_report_urls=cdn_report_urls, cdn_card_urls=cdn_card_urls,
        )
    else:
        context = _build_context(business_name, report_type, summary, report_url, social_handles, cdn_report_urls)
    logger.info(f"[SocialPostGen] Generating 5-channel content for {business_name} ({report_type})")

    try:
        session_service = InMemorySessionService()
        session_id = f"social-posts-{int(time.time() * 1000)}"

        await session_service.create_session(
            app_name="hephae-hub", session_id=session_id, user_id="sys", state={}
        )

        runner = Runner(
            app_name="hephae-hub",
            agent=social_post_parallel,
            session_service=session_service,
        )

        async for _ in runner.run_async(
            session_id=session_id, user_id="sys", new_message=user_msg(context),
        ):
            pass

        # Read all outputs from session state
        session = await session_service.get_session(
            app_name="hephae-hub", session_id=session_id, user_id="sys"
        )
        state = session.state or {}

        ig_data = _parse_json(state.get("instagramPost", "{}"))
        fb_data = _parse_json(state.get("facebookPost", "{}"))
        tw_data = _parse_json(state.get("twitterPost", "{}"))
        email_data = _parse_json(state.get("emailOutreach", "{}"))
        contact_data = _parse_json(state.get("contactFormDraft", "{}"))

        result = {
            "instagram": {
                "caption": ig_data.get("caption", ""),
                "reportLink": ig_data.get("reportLink", ""),
                "imageUrl": ig_data.get("imageUrl", ""),
            },
            "facebook": {
                "post": fb_data.get("post", ""),
                "reportLink": fb_data.get("reportLink", ""),
                "imageUrl": fb_data.get("imageUrl", ""),
            },
            "twitter": {
                "tweet": tw_data.get("tweet", ""),
                "reportLink": tw_data.get("reportLink", ""),
                "imageUrl": tw_data.get("imageUrl", ""),
            },
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
