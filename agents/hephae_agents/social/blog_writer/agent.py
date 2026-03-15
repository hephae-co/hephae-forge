"""
Blog writer agents — ResearchCompiler + BlogWriter as SequentialAgent.

Pipeline: ResearchCompiler → BlogWriter (via session state).
Generates full authoritative blog posts (800-1200 words) from Firestore latestOutputs.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_db.schemas.agent_outputs import BlogResearchOutput
from hephae_agents.social.blog_writer.prompts import (
    RESEARCH_COMPILER_INSTRUCTION,
    BLOG_WRITER_INSTRUCTION,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report type labels
# ---------------------------------------------------------------------------

REPORT_TYPE_LABELS = {
    "margin_surgeon": "Margin Surgery",
    "seo_auditor": "SEO Deep Audit",
    "traffic_forecaster": "Foot Traffic Forecast",
    "competitive_analyzer": "Competitive Analysis",
    "marketing_swarm": "Social Media Insights",
}


# ---------------------------------------------------------------------------
# Dynamic instructions (Phase 3)
# ---------------------------------------------------------------------------


def _research_instruction(ctx):
    """Dynamic instruction — reads data context from session state."""
    parts = [RESEARCH_COMPILER_INSTRUCTION]
    data_context = ctx.state.get("dataContext", "")
    if data_context:
        parts.append(f"\n\n{data_context}")
    return "\n".join(parts)


def _writer_instruction(ctx):
    """Dynamic instruction — reads research brief from session state."""
    parts = [BLOG_WRITER_INSTRUCTION]
    brief = ctx.state.get("researchBrief", "")
    if brief:
        parts.append(f"\n\nResearch Brief:\n{brief}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

research_compiler_agent = LlmAgent(
    name="ResearchCompilerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_research_instruction,
    output_key="researchBrief",
    output_schema=BlogResearchOutput,
    on_model_error_callback=fallback_on_error,
)

blog_writer_agent = LlmAgent(
    name="BlogWriterAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    instruction=_writer_instruction,
    output_key="blogContent",
    on_model_error_callback=fallback_on_error,
)

blog_pipeline = SequentialAgent(
    name="BlogPipeline",
    description="2-stage blog generation: compile research → write blog post.",
    sub_agents=[research_compiler_agent, blog_writer_agent],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def _build_data_context(
    business_name: str,
    latest_outputs: dict[str, Any],
) -> str:
    """Build structured data context from latestOutputs for the research compiler."""
    parts = [
        f"Business: {business_name}",
        f"Available Reports: {', '.join(REPORT_TYPE_LABELS.get(k, k) for k in latest_outputs if isinstance(latest_outputs.get(k), dict))}",
    ]

    m = latest_outputs.get("margin_surgeon")
    if m and isinstance(m, dict):
        parts.append("\n## Margin Surgery Data")
        if m.get("score") is not None:
            parts.append(f"Overall Score: {m['score']}/100")
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
            parts.append(f"Report URL: {m['reportUrl']}")

    s = latest_outputs.get("seo_auditor")
    if s and isinstance(s, dict):
        parts.append("\n## SEO Audit Data")
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
            parts.append(f"Report URL: {s['reportUrl']}")

    t = latest_outputs.get("traffic_forecaster")
    if t and isinstance(t, dict):
        parts.append("\n## Traffic Forecast Data")
        if t.get("peak_slot_score") is not None:
            parts.append(f"Peak Traffic Score: {t['peak_slot_score']}")
        if t.get("summary"):
            parts.append(f"Summary: {t['summary']}")
        if t.get("reportUrl"):
            parts.append(f"Report URL: {t['reportUrl']}")

    c = latest_outputs.get("competitive_analyzer")
    if c and isinstance(c, dict):
        parts.append("\n## Competitive Analysis Data")
        if c.get("competitor_count") is not None:
            parts.append(f"Competitors Analyzed: {c['competitor_count']}")
        if c.get("avg_threat_level") is not None:
            parts.append(f"Avg Threat Level: {c['avg_threat_level']}/10")
        if c.get("summary"):
            parts.append(f"Summary: {c['summary']}")
        if c.get("reportUrl"):
            parts.append(f"Report URL: {c['reportUrl']}")

    mk = latest_outputs.get("marketing_swarm")
    if mk and isinstance(mk, dict):
        parts.append("\n## Marketing Insights Data")
        if mk.get("summary"):
            parts.append(f"Summary: {mk['summary']}")
        if mk.get("reportUrl"):
            parts.append(f"Report URL: {mk['reportUrl']}")

    return "\n".join(parts)


def _parse_json(raw: str) -> dict:
    """Extract JSON from agent output, stripping markdown fences."""
    if isinstance(raw, dict):
        return raw
    cleaned = re.sub(r"```json\n?|\n?```", "", str(raw)).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_blog_post(
    business_name: str,
    latest_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Generate a full blog post via SequentialAgent pipeline.

    Args:
        business_name: Name of the business.
        latest_outputs: Dict of agent outputs from Firestore latestOutputs.

    Returns:
        {
            "title": "Blog post title",
            "html_content": "<h1>...</h1><p>...</p>...",
            "research_brief": {...},
            "word_count": int,
            "data_sources": ["margin_surgeon", "seo_auditor", ...],
        }
    """
    session_service = InMemorySessionService()
    data_context = _build_data_context(business_name, latest_outputs)

    logger.info(f"[BlogWriter] Starting pipeline for {business_name}")

    session_id = f"blog-{int(time.time() * 1000)}"

    # Pre-populate session state for dynamic instructions
    await session_service.create_session(
        app_name="hephae-hub",
        session_id=session_id,
        user_id="sys",
        state={"dataContext": data_context},
    )

    runner = Runner(
        app_name="hephae-hub",
        agent=blog_pipeline,
        session_service=session_service,
    )

    async for _ in runner.run_async(
        session_id=session_id,
        user_id="sys",
        new_message=user_msg("Compile research and write blog post."),
    ):
        pass

    # Read outputs from session state
    session = await session_service.get_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys"
    )
    state = session.state or {}
    research_brief = _parse_json(state.get("researchBrief", "{}"))
    blog_html = str(state.get("blogContent", ""))

    # Clean up: strip any markdown/json fences
    blog_html = re.sub(r"```(?:html)?\n?|\n?```", "", blog_html).strip()

    # Extract title from <h1> tag
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", blog_html, re.DOTALL)
    title = title_match.group(1).strip() if title_match else f"Hephae Analysis: {business_name}"
    title = re.sub(r"<[^>]+>", "", title)

    # Count words (strip HTML tags for counting)
    plain_text = re.sub(r"<[^>]+>", " ", blog_html)
    word_count = len(plain_text.split())

    # Track which data sources were used
    data_sources = [k for k in latest_outputs if isinstance(latest_outputs.get(k), dict)]

    logger.info(
        f"[BlogWriter] Done: title='{title[:60]}', words={word_count}, sources={data_sources}"
    )

    return {
        "title": title,
        "html_content": blog_html,
        "research_brief": research_brief,
        "word_count": word_count,
        "data_sources": data_sources,
    }
