"""ReviewerAgent — scores a business for outreach readiness.

Takes a business's identity + all latest capability outputs and produces a
structured outreach readiness assessment stored at latestOutputs.reviewer.

Score interpretation:
  8-10: Prime candidate — reach out immediately
  5-7:  Moderate fit — worth considering
  1-4:  Poor fit — skip or revisit later
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai.types import Content, Part

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)

_REVIEWER_INSTRUCTION = """You are a business outreach readiness reviewer for Hephae, an AI-powered
restaurant and local business intelligence platform.

Your job is to evaluate a business and score how suitable they are for a sales outreach from Hephae.
Hephae helps independent local businesses with:
- SEO optimization and web presence
- Competitive positioning against local rivals
- Menu pricing and margin improvement
- Social media strategy
- Traffic and demand forecasting

A HIGH-SCORING business (8-10) is one that:
- Has clear, solvable problems (poor SEO score, thin social presence, margin issues)
- Is an independent business that can make decisions (not a chain or franchise)
- Has at least one good contact channel (email preferred, then Instagram/Twitter, then phone)
- Has enough digital presence to benefit from our services (has website or social media)

A LOW-SCORING business (1-4) is one that:
- Has no problems (already excellent across the board)
- Is a chain/franchise (can't benefit from our personalized approach)
- Has no contact channels at all (can't be reached)
- Is too small or digital-free to benefit

Call record_review() with your assessment. Be specific and actionable in your reasoning.
Always identify the BEST channel to reach them first."""


def _make_review_tool(result_container: list) -> FunctionTool:
    def record_review(
        outreach_score: int,
        best_channel: str,
        primary_reason: str,
        strengths: list[str],
        concerns: list[str],
    ) -> str:
        """Record the outreach readiness review.

        Args:
            outreach_score: 1-10 integer (10 = perfect outreach candidate, 1 = skip entirely)
            best_channel: Best channel to reach them — one of: "email", "instagram", "twitter", "phone", "website_form", "none"
            primary_reason: One-sentence explanation of the score
            strengths: List of reasons to reach out (problems Hephae can solve, contact availability)
            concerns: List of blockers or concerns (already solved, no contact, chain, etc.)
        """
        result_container.append({
            "outreach_score": max(1, min(10, int(outreach_score))),
            "best_channel": best_channel,
            "primary_reason": primary_reason,
            "strengths": strengths or [],
            "concerns": concerns or [],
        })
        return "Review recorded."

    return FunctionTool(func=record_review)


def _build_reviewer_prompt(biz_id: str, identity: dict[str, Any], latest_outputs: dict[str, Any]) -> str:
    lines = [f"## Business Profile: {identity.get('name', biz_id)}"]

    # Contact channels
    email = identity.get("email") or ""
    phone = identity.get("phone") or ""
    website = identity.get("officialUrl") or identity.get("website") or ""
    social = identity.get("socialLinks") or {}

    lines.append("\n### Contact Channels")
    lines.append(f"- Email: {email or 'not found'}")
    lines.append(f"- Phone: {phone or 'not found'}")
    lines.append(f"- Website: {website or 'none'}")
    lines.append(f"- Instagram: {social.get('instagram') or 'none'}")
    lines.append(f"- Twitter/X: {social.get('twitter') or 'none'}")

    # Business basics
    category = identity.get("category") or ""
    if category:
        lines.append(f"\n### Category: {category}")

    ai_overview = identity.get("aiOverview") or {}
    if isinstance(ai_overview, dict) and ai_overview.get("summary"):
        lines.append(f"\n### Business Overview\n{ai_overview['summary'][:300]}")

    # Capability scores summary
    lines.append("\n### Analysis Results")
    score_map = {
        "seo_auditor": "SEO Audit",
        "traffic_forecaster": "Traffic Forecast",
        "competitive_analyzer": "Competitive Analysis",
        "margin_surgeon": "Margin Surgery",
        "social_media_auditor": "Social Media Audit",
    }
    if latest_outputs:
        for key, label in score_map.items():
            output = latest_outputs.get(key)
            if not output or not isinstance(output, dict):
                continue
            score = output.get("score") or output.get("overallScore") or output.get("overall_score")
            summary = (output.get("summary") or "")[:150]
            lines.append(f"- {label}: score={score}/100 — {summary}")
    else:
        lines.append("- No capability analysis run yet")

    lines.append(
        "\n\nScore this business's outreach readiness (1-10) and call record_review() with your assessment."
    )
    return "\n".join(lines)


async def run_reviewer(
    biz_id: str,
    identity: dict[str, Any],
    latest_outputs: dict[str, Any],
) -> dict[str, Any] | None:
    """Run the reviewer agent. Returns the review dict or None on failure."""
    result_container: list[dict] = []
    review_tool = _make_review_tool(result_container)

    agent = LlmAgent(
        name="ReviewerAgent",
        model=AgentModels.PRIMARY_MODEL,
        instruction=_REVIEWER_INSTRUCTION,
        tools=[review_tool],
        on_model_error_callback=fallback_on_error,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="hephae-hub",
        agent=agent,
        session_service=session_service,
    )

    session_id = f"reviewer-{biz_id}-{int(time.time() * 1000)}"
    await session_service.create_session(
        app_name="hephae-hub", user_id="system", session_id=session_id, state={}
    )

    prompt = _build_reviewer_prompt(biz_id, identity, latest_outputs)

    try:
        async for _ in runner.run_async(
            user_id="system",
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            pass
    except Exception as e:
        logger.warning(f"[Reviewer] Agent error for {biz_id}: {e}")
        return None

    if not result_container:
        logger.warning(f"[Reviewer] No review recorded for {biz_id}")
        return None

    return result_container[0]
