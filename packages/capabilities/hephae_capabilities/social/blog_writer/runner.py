"""Blog Writer runner — delegates to generate_blog_post() which already implements the runner pattern."""

from __future__ import annotations

from typing import Any

from hephae_capabilities.social.blog_writer.agent import generate_blog_post


async def run_blog_generation(
    identity: dict[str, Any],
    business_context: Any | None = None,
    *,
    latest_outputs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate a blog post from stored analysis data.

    Args:
        identity: Identity dict (needs name).
        business_context: Unused.
        latest_outputs: Dict of agent outputs from Firestore latestOutputs.

    Returns:
        {title, html_content, research_brief, word_count, data_sources}
    """
    business_name = identity.get("name", "")
    if not business_name:
        raise ValueError("Missing business name for blog generation")
    if not latest_outputs:
        raise ValueError("No analysis data provided for blog generation")

    return await generate_blog_post(business_name, latest_outputs)
