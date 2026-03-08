"""Eval prompt builders — reconstruct agent input prompts from saved fixture identity.

Each builder returns the exact string that would be sent to the eval agent's
root_agent as user_content. These mirror the prompts used in the real runners
so that human-curated eval cases exercise the same code path.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def build_eval_prompt(agent_key: str, identity: dict[str, Any], fixture: dict[str, Any] = None) -> str:
    """Return the agent input prompt for a given agent and business identity.

    Args:
        agent_key: Firestore output key (e.g. "seo_auditor", "margin_surgeon").
        identity: Business identity dict from the fixture.
        fixture: Full fixture dict (used by agents that need latestOutputs as input).

    Returns:
        Prompt string to use as user_content in the eval case.
    """
    fixture = fixture or {}
    builder = _BUILDERS.get(agent_key)
    if not builder:
        # Generic fallback
        return (
            f"Analyze this business: {identity.get('name', 'Unknown')} "
            f"at {identity.get('address', 'unknown location')}."
        )
    return builder(identity, fixture)


def _build_seo_prompt(identity: dict, fixture: dict) -> str:
    url = identity.get("officialUrl", "")
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    if url:
        return (
            f"Execute a full SEO Deep Dive on {url}. "
            "Evaluate technical SEO, content quality, user experience, performance, and backlinks."
        )
    return (
        f"Perform a comprehensive SEO audit for {name} located at {address}. "
        "Search to find their online presence. "
        "Evaluate technical SEO, content quality, UX, performance, and authority. Return a JSON report."
    )


def _build_traffic_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    coords = identity.get("coordinates") or {}
    lat = coords.get("lat", 0)
    lng = coords.get("lng", 0)
    today = datetime.now().strftime("%A, %B %d, %Y")
    return (
        f"Business: {name}\n"
        f"Location: {address}\n"
        f"Latitude: {lat}\n"
        f"Longitude: {lng}\n"
        f"Today: {today}\n\n"
        "Please gather intelligence context."
    )


def _build_competitive_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    category = identity.get("category", "local business")
    competitors = identity.get("competitors", [])
    parts = [
        f"Perform a competitive analysis for {name} located at {address}.",
        f"Category: {category}.",
    ]
    if competitors:
        parts.append(f"Known competitors from discovery: {json.dumps(competitors[:10])}.")
    parts.append(
        "Find and profile all direct competitors within 1 mile. "
        "Analyze the competitive landscape and synthesize market positioning recommendations. "
        "Return a detailed JSON report."
    )
    return " ".join(parts)


def _build_margin_surgeon_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    menu_data = identity.get("menuData") or {}
    if menu_data:
        menu_str = json.dumps(menu_data, indent=2)
    else:
        menu_str = "(no menu data available — extract from business context)"
    return (
        f"Perform a full margin surgery analysis for {name} located at {address}.\n\n"
        f"Menu data:\n{menu_str}\n\n"
        "Extract menu items, benchmark against competitors, analyze commodity trends, "
        "identify profit leakage, and provide strategic pricing recommendations. "
        "Return a JSON report with overall_score, menu_items, and strategic_advice."
    )


def _build_social_media_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    parts = [f"Business: {name}"]
    if address:
        parts.append(f"Location: {address}")
    if identity.get("persona"):
        parts.append(f"Persona: {identity['persona']}")
    if identity.get("officialUrl"):
        parts.append(f"Website: {identity['officialUrl']}")
    social = identity.get("socialLinks") or {}
    active_social = {k: v for k, v in social.items() if v}
    if active_social:
        parts.append(f"\nKNOWN SOCIAL LINKS:\n{json.dumps(active_social, indent=2)}")
    competitors = identity.get("competitors", [])
    if competitors:
        parts.append(f"\nCOMPETITORS:\n{json.dumps(competitors[:5])}")
    parts.append(
        "\nAudit all social media platforms. Research their presence, analyze content strategy "
        "and engagement, and synthesize recommendations. Return a JSON audit report."
    )
    return "\n".join(parts)


def _build_discovery_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    url = identity.get("officialUrl", "")
    lines = [
        "Discover and profile this business:",
        f"Name: {name}",
        f"Address: {address}",
    ]
    if url:
        lines.append(f"Website: {url}")
    lines.append(
        "\nCrawl their website, extract all business details (theme, contact, social links, "
        "menu, maps data, competitors, news), discover social profiles, and validate all URLs found."
    )
    return "\n".join(lines)


def _build_blog_writer_prompt(identity: dict, fixture: dict) -> str:
    name = identity.get("name", "Unknown")
    latest_outputs = fixture.get("latestOutputs", {})
    available = [k for k, v in latest_outputs.items() if isinstance(v, dict)]

    parts = [
        f"Business: {name}",
        f"Available Reports: {', '.join(available) if available else 'none'}",
    ]

    # Mirror the data context format from blog_writer/agent.py without importing it
    for agent_key, label in [
        ("margin_surgeon", "Margin Surgery"),
        ("seo_auditor", "SEO Audit"),
        ("traffic_forecaster", "Foot Traffic Forecast"),
        ("competitive_analyzer", "Competitive Analysis"),
        ("social_media_auditor", "Social Media Insights"),
    ]:
        data = latest_outputs.get(agent_key)
        if not data or not isinstance(data, dict):
            continue
        parts.append(f"\n## {label} Data")
        if data.get("score") is not None or data.get("overall_score") is not None:
            score = data.get("score") or data.get("overall_score")
            parts.append(f"Overall Score: {score}/100")
        if data.get("summary"):
            parts.append(f"Summary: {data['summary']}")

    return "\n".join(parts)


_BUILDERS: dict[str, Any] = {
    "seo_auditor": _build_seo_prompt,
    "traffic_forecaster": _build_traffic_prompt,
    "competitive_analyzer": _build_competitive_prompt,
    "margin_surgeon": _build_margin_surgeon_prompt,
    "social_media_auditor": _build_social_media_prompt,
    "discovery_pipeline": _build_discovery_prompt,
    "blog_writer": _build_blog_writer_prompt,
}

# Maps agentKey (Firestore output key) to the eval agent module path
AGENT_EVAL_MODULE: dict[str, str] = {
    "seo_auditor": "tests.evals.seo_auditor.agent",
    "traffic_forecaster": "tests.evals.traffic_forecaster.agent",
    "competitive_analyzer": "tests.evals.competitive_analyzer.agent",
    "margin_surgeon": "tests.evals.margin_surgeon_capability.agent",
    "social_media_auditor": "tests.evals.social_media_auditor.agent",
    "discovery_pipeline": "tests.evals.discovery_pipeline.agent",
    "blog_writer": "tests.evals.blog_writer.agent",
}
