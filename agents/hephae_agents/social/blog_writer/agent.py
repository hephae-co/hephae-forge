"""
Blog writer agents — 5-stage pipeline with charts, SEO, and critique.

Pipeline:
  ResearchCompiler → BlogWriter (with chart tools) → SEOEnricher → BlogCritique
  If critique fails: BlogWriter reruns with rewrite instructions (max 1 retry).
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
from google.adk.tools import FunctionTool

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_db.schemas.agent_outputs import BlogResearchOutput
from hephae_agents.social.blog_writer.prompts import (
    RESEARCH_COMPILER_INSTRUCTION,
    BLOG_WRITER_INSTRUCTION,
    BLOG_CRITIQUE_INSTRUCTION,
    SEO_ENRICHER_INSTRUCTION,
)
from hephae_agents.social.blog_writer.tools import (
    generate_chart_js,
    inject_seo_meta,
    inject_social_share,
    inject_schema_org,
    generate_chartjs_library_tag,
)

logger = logging.getLogger(__name__)

REPORT_TYPE_LABELS = {
    "margin_surgeon": "Margin Surgery",
    "seo_auditor": "SEO Deep Audit",
    "traffic_forecaster": "Foot Traffic Forecast",
    "competitive_analyzer": "Competitive Analysis",
    "marketing_swarm": "Social Media Insights",
}

# ---------------------------------------------------------------------------
# Tools (wrapped as ADK FunctionTool)
# ---------------------------------------------------------------------------

chart_tool = FunctionTool(func=generate_chart_js)

# ---------------------------------------------------------------------------
# Dynamic instructions
# ---------------------------------------------------------------------------


def _research_instruction(ctx):
    parts = [RESEARCH_COMPILER_INSTRUCTION]
    data_context = ctx.state.get("dataContext", "")
    if data_context:
        parts.append(f"\n\n{data_context}")
    return "\n".join(parts)


def _writer_instruction(ctx):
    parts = [BLOG_WRITER_INSTRUCTION]
    brief = ctx.state.get("researchBrief", "")
    if brief:
        parts.append(f"\n\nResearch Brief:\n{brief}")
    rewrite = ctx.state.get("rewriteInstructions", "")
    if rewrite:
        parts.append(f"\n\nREWRITE REQUIRED — fix these issues:\n{rewrite}")
    return "\n".join(parts)


def _critique_instruction(ctx):
    import json as _json
    parts = [BLOG_CRITIQUE_INSTRUCTION]
    blog = ctx.state.get("blogContent", "")
    brief = ctx.state.get("researchBrief", "")
    if blog:
        blog_str = str(blog)[:8000] if isinstance(blog, str) else str(blog)[:8000]
        parts.append(f"\n\nBLOG HTML TO REVIEW:\n{blog_str}")
    if brief:
        brief_str = _json.dumps(brief, default=str)[:4000] if isinstance(brief, dict) else str(brief)[:4000]
        parts.append(f"\n\nORIGINAL RESEARCH DATA:\n{brief_str}")
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
    tools=[chart_tool],
    output_key="blogContent",
    on_model_error_callback=fallback_on_error,
)

seo_enricher_agent = LlmAgent(
    name="SEOEnricherAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=SEO_ENRICHER_INSTRUCTION,
    output_key="seoMeta",
    on_model_error_callback=fallback_on_error,
)

blog_critique_agent = LlmAgent(
    name="BlogCritiqueAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.MEDIUM,
    instruction=_critique_instruction,
    output_key="critiqueResult",
    on_model_error_callback=fallback_on_error,
)

blog_pipeline = SequentialAgent(
    name="BlogPipeline",
    description="5-stage blog generation: research → write (with charts) → SEO → critique.",
    sub_agents=[
        research_compiler_agent,
        blog_writer_agent,
        seo_enricher_agent,
        blog_critique_agent,
    ],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


def _build_data_context(
    subject: str,
    latest_outputs: dict[str, Any] | None = None,
    pulse_data: dict[str, Any] | None = None,
    industry_pulse: dict[str, Any] | None = None,
) -> str:
    """Build data context from any combination of sources."""
    parts = [f"Subject: {subject}"]

    # Pulse data (from zipcode_weekly_pulse)
    if pulse_data:
        parts.append("\n## Weekly Pulse Data")
        pulse = pulse_data.get("pulse", {})
        if pulse.get("headline"):
            parts.append(f"Headline: {pulse['headline']}")
        insights = pulse.get("insights", [])
        if insights:
            parts.append(f"Insights ({len(insights)}):")
            for ins in insights[:5]:
                parts.append(f"  - [{ins.get('impactScore', '?')}] {ins.get('title', '?')}")
                parts.append(f"    Analysis: {ins.get('analysis', '')[:200]}")
                parts.append(f"    Sources: {ins.get('signalSources', [])}")

        # Pre-computed impact variables
        pd = pulse_data.get("pipelineDetails", {})
        impact = pd.get("preComputedImpact", {})
        if impact:
            parts.append(f"\nPre-Computed Impact Variables ({len(impact)}):")
            for k, v in sorted(impact.items()):
                if isinstance(v, (int, float)):
                    parts.append(f"  {k}: {v}")

        # Local briefing
        lb = pulse.get("localBriefing", {})
        if lb:
            events = lb.get("thisWeekInTown", [])
            competitors = lb.get("competitorWatch", [])
            buzz = lb.get("communityBuzz", "")
            if events:
                parts.append(f"\nLocal Events ({len(events)}):")
                for e in events[:3]:
                    parts.append(f"  - {e.get('what', '?')} @ {e.get('where', '?')}")
            if competitors:
                parts.append(f"\nCompetitor Watch ({len(competitors)}):")
                for c in competitors[:3]:
                    parts.append(f"  - {c.get('name', c.get('business', '?'))}: {c.get('observation', c.get('note', ''))[:100]}")
            if buzz:
                parts.append(f"\nCommunity Buzz: {buzz[:200]}")

        # Quick stats
        qs = pulse.get("quickStats", {})
        if qs:
            parts.append(f"\nQuick Stats: {json.dumps(qs)}")

    # Industry pulse (from industry_pulses)
    if industry_pulse:
        parts.append("\n## Industry Pulse (National)")
        if industry_pulse.get("trendSummary"):
            parts.append(f"Trend Summary: {industry_pulse['trendSummary'][:500]}")
        ni = industry_pulse.get("nationalImpact", {})
        if ni:
            parts.append(f"\nNational Impact Variables ({len(ni)}):")
            for k, v in sorted(ni.items()):
                if isinstance(v, (int, float)):
                    parts.append(f"  {k}: {v}")
        playbooks = industry_pulse.get("nationalPlaybooks", [])
        if playbooks:
            parts.append(f"\nTriggered Playbooks ({len(playbooks)}):")
            for p in playbooks:
                parts.append(f"  - {p.get('name', '?')}: {p.get('play', '')[:120]}")

    # Legacy: business-level latestOutputs
    if latest_outputs:
        for key, label in REPORT_TYPE_LABELS.items():
            data = latest_outputs.get(key)
            if data and isinstance(data, dict):
                parts.append(f"\n## {label}")
                for field in ("score", "summary", "totalLeakage", "menu_item_count",
                              "competitor_count", "avg_threat_level", "peak_slot_score", "reportUrl"):
                    if data.get(field) is not None:
                        parts.append(f"  {field}: {data[field]}")

    return "\n".join(parts)


def _parse_json(raw: str) -> dict:
    if isinstance(raw, dict):
        return raw
    cleaned = re.sub(r"```(?:json)?\n?|\n?```", "", str(raw)).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


async def generate_blog_post(
    business_name: str,
    latest_outputs: dict[str, Any] | None = None,
    pulse_data: dict[str, Any] | None = None,
    industry_pulse: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a full blog post with charts, SEO, and critique.

    Accepts data from any combination of:
    - latest_outputs: business-level agent outputs (legacy)
    - pulse_data: zipcode weekly pulse document
    - industry_pulse: industry pulse document

    Returns:
        {
            "title": str,
            "html_content": str (article HTML with charts),
            "seo_meta": str (meta tags for <head>),
            "social_share": str (share buttons HTML),
            "schema_org": str (JSON-LD),
            "chartjs_tag": str (CDN script tag),
            "research_brief": dict,
            "critique": dict,
            "word_count": int,
            "chart_count": int,
            "data_sources": list[str],
        }
    """
    session_service = InMemorySessionService()
    data_context = _build_data_context(
        business_name, latest_outputs, pulse_data, industry_pulse,
    )

    logger.info(f"[BlogWriter] Starting pipeline for {business_name}")
    session_id = f"blog-{int(time.time() * 1000)}"

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
        new_message=user_msg("Compile research, write blog post with charts, generate SEO metadata, and critique."),
    ):
        pass

    # Read outputs
    session = await session_service.get_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys",
    )
    state = session.state or {}

    research_brief = _parse_json(state.get("researchBrief", "{}"))
    blog_html = str(state.get("blogContent", ""))
    seo_meta_raw = _parse_json(state.get("seoMeta", "{}"))
    critique = _parse_json(state.get("critiqueResult", "{}"))

    # Clean up HTML — strip markdown fences
    blog_html = re.sub(r"```(?:html)?\n?|\n?```", "", blog_html).strip()

    # Strip any SEO/critique metadata that leaked into the article body
    # These agents write to separate output_keys but their text sometimes
    # gets appended to the blog content in the session conversation history
    for marker in ["<h2>SEO Metadata</h2>", "<h2>Blog Critique</h2>",
                    "SEO Metadata\n", "Blog Critique\n",
                    "## SEO Metadata", "## Blog Critique"]:
        idx = blog_html.find(marker)
        if idx > 0:
            logger.warning(f"[BlogWriter] Stripping leaked metadata at char {idx}: {marker[:30]}")
            blog_html = blog_html[:idx].rstrip()

    # If critique failed and we have rewrite instructions, run writer again
    if not critique.get("overall_pass", True) and critique.get("rewrite_instructions"):
        logger.warning(f"[BlogWriter] Critique failed — rerunning writer with fixes")
        state["rewriteInstructions"] = critique["rewrite_instructions"]

        rewrite_runner = Runner(
            app_name="hephae-hub",
            agent=blog_writer_agent,
            session_service=session_service,
        )
        async for _ in rewrite_runner.run_async(
            session_id=session_id,
            user_id="sys",
            new_message=user_msg("Rewrite the blog fixing the critique issues."),
        ):
            pass

        session = await session_service.get_session(
            app_name="hephae-hub", session_id=session_id, user_id="sys",
        )
        blog_html = str((session.state or {}).get("blogContent", blog_html))
        blog_html = re.sub(r"```(?:html)?\n?|\n?```", "", blog_html).strip()

    # Final cleanup — strip any metadata that leaked into article body
    for marker in ["<h2>SEO Metadata</h2>", "<h2>Blog Critique</h2>",
                    "SEO Metadata\n", "Blog Critique\n",
                    "## SEO Metadata", "## Blog Critique",
                    "<h3>SEO Metadata</h3>", "<h3>Blog Critique</h3>"]:
        idx = blog_html.find(marker)
        if idx > 0:
            logger.warning(f"[BlogWriter] Final strip of leaked metadata: {marker[:30]}")
            blog_html = blog_html[:idx].rstrip()

    # Inject charts deterministically from research brief data
    # (LLM tool calling is unreliable — sometimes the model calls the tool, sometimes not)
    chart_suggestions = research_brief.get("chart_suggestions", [])
    if chart_suggestions and blog_html.count('class="chart-container"') == 0:
        logger.info(f"[BlogWriter] Injecting {len(chart_suggestions)} charts from research brief")
        chart_html_blocks = []
        for i, cs in enumerate(chart_suggestions[:3]):
            try:
                block = generate_chart_js(
                    chart_id=f"chart{i + 1}",
                    chart_type=cs.get("type", "bar"),
                    title=cs.get("title", f"Chart {i + 1}"),
                    labels=cs.get("labels", []),
                    values=cs.get("values", []),
                    caption=cs.get("caption", ""),
                    dataset_label=cs.get("dataset_label", ""),
                )
                chart_html_blocks.append(block)
            except Exception as e:
                logger.warning(f"[BlogWriter] Chart {i + 1} generation failed: {e}")

        if chart_html_blocks:
            # Insert charts after the first <h2> section
            h2_match = re.search(r"</p>\s*<h2", blog_html)
            if h2_match:
                insert_pos = h2_match.start() + 4  # after </p>
                charts_combined = "\n\n".join(chart_html_blocks)
                blog_html = blog_html[:insert_pos] + f"\n\n{charts_combined}\n\n" + blog_html[insert_pos:]
            else:
                # Fallback: append before closing
                blog_html += "\n\n" + "\n\n".join(chart_html_blocks)

    # Extract title
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", blog_html, re.DOTALL)
    title = title_match.group(1).strip() if title_match else f"Hephae Analysis: {business_name}"
    title = re.sub(r"<[^>]+>", "", title)

    # Count words and charts
    plain_text = re.sub(r"<[^>]+>", " ", blog_html)
    word_count = len(plain_text.split())
    chart_count = blog_html.count('class="chart-container"')

    # Generate SEO assets using tools
    seo_title = seo_meta_raw.get("title_tag", title)
    seo_desc = seo_meta_raw.get("meta_description", f"Data-driven analysis of {business_name} by Hephae Intelligence.")
    seo_keywords = seo_meta_raw.get("keywords", [])
    slug = seo_meta_raw.get("slug", re.sub(r"[^a-z0-9]+", "-", business_name.lower()).strip("-"))

    # These will be populated with real URLs after CDN upload
    placeholder_url = f"https://cdn.hephae.co/reports/{slug}/blog.html"

    seo_meta_html = inject_seo_meta(
        title=seo_title,
        description=seo_desc,
        keywords=seo_keywords,
        canonical_url=placeholder_url,
    )
    social_share_html = inject_social_share(title=title, url=placeholder_url)
    schema_org_html = inject_schema_org(
        title=title,
        description=seo_desc,
        url=placeholder_url,
        word_count=word_count,
    )

    data_sources = []
    if pulse_data:
        data_sources.extend(pulse_data.get("signalsUsed", []))
    if industry_pulse:
        data_sources.extend(industry_pulse.get("signalsUsed", []))
    if latest_outputs:
        data_sources.extend(k for k in latest_outputs if isinstance(latest_outputs.get(k), dict))
    data_sources = list(set(data_sources))

    logger.info(
        f"[BlogWriter] Done: title='{title[:60]}', words={word_count}, "
        f"charts={chart_count}, critique={'PASS' if critique.get('overall_pass') else 'FAIL'}"
    )

    return {
        "title": title,
        "html_content": blog_html,
        "seo_meta": seo_meta_html,
        "social_share": social_share_html,
        "schema_org": schema_org_html,
        "chartjs_tag": generate_chartjs_library_tag(),
        "seo_keywords": seo_keywords,
        "seo_description": seo_desc,
        "slug": slug,
        "research_brief": research_brief,
        "critique": critique,
        "word_count": word_count,
        "chart_count": chart_count,
        "data_sources": data_sources,
    }
