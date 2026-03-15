"""Social Post Generator runner — delegates to generate_social_posts()."""

from __future__ import annotations

from typing import Any

from hephae_agents.social.post_generator.agent import generate_social_posts


async def run_social_post_generation(
    identity: dict[str, Any],
    business_context: Any | None = None,
    *,
    report_type: str = "",
    summary: str = "",
    report_url: str = "",
    social_handles: dict[str, str] | None = None,
    latest_outputs: dict[str, Any] | None = None,
    cdn_report_urls: dict[str, str] | None = None,
    cdn_card_urls: dict[str, str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate outreach content for Instagram, Facebook, X/Twitter, Email, and Contact Form.

    Args:
        identity: Identity dict (needs name).
        business_context: Unused.
        report_type: Type of report to highlight.
        summary: Legacy single summary string.
        report_url: URL of the full report.
        social_handles: Known social handles.
        latest_outputs: Rich data from Firestore latestOutputs.
        cdn_report_urls: Map of report_type -> CDN URL for report links.
        cdn_card_urls: Map of report_type -> CDN URL for social card images.

    Returns:
        {
            instagram: {caption, reportLink, imageUrl},
            facebook: {post, reportLink, imageUrl},
            twitter: {tweet, reportLink, imageUrl},
            email: {subject, body},
            contactForm: {message}
        }
    """
    business_name = identity.get("name", "")
    if not business_name:
        raise ValueError("Missing business name for social post generation")

    return await generate_social_posts(
        business_name=business_name,
        report_type=report_type,
        summary=summary,
        report_url=report_url,
        social_handles=social_handles,
        latest_outputs=latest_outputs,
        cdn_report_urls=cdn_report_urls,
        cdn_card_urls=cdn_card_urls,
    )
