"""
DiscoveryPipeline — three-stage discovery:
  Stage 1: SiteCrawlerAgent crawls the business URL once -> rawSiteData
  Stage 2: DiscoveryFanOut fans out to 6 specialized agents reading rawSiteData
  Stage 3: SocialProfilerAgent crawls social profiles found in Stage 2 -> socialProfileMetrics

Port of src/agents/discovery/pipeline.ts.
Uses Google ADK Python SDK (LlmAgent, ParallelAgent, SequentialAgent).
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from backend.config import AgentModels
from backend.agents.shared_tools import (
    google_search_tool,
    playwright_tool,
    crawl4ai_tool,
    crawl4ai_advanced_tool,
    crawl4ai_deep_tool,
)
from backend.agents.discovery.prompts import (
    SITE_CRAWLER_INSTRUCTION,
    THEME_AGENT_INSTRUCTION,
    CONTACT_AGENT_INSTRUCTION,
    SOCIAL_MEDIA_AGENT_INSTRUCTION,
    MENU_AGENT_INSTRUCTION,
    MAPS_AGENT_INSTRUCTION,
    COMPETITOR_AGENT_INSTRUCTION,
    SOCIAL_PROFILER_INSTRUCTION,
)


# ---------------------------------------------------------------------------
# Helper: inject rawSiteData from session state into instruction
# ---------------------------------------------------------------------------

def _with_raw_data(base_instruction: str):
    """Build dynamic instruction that injects rawSiteData from session state."""

    def build_instruction(context) -> str:
        raw = getattr(context, "state", {}).get("rawSiteData", {})
        raw_str = raw if isinstance(raw, str) else json.dumps(raw or {})
        # Truncate to avoid context window bloat
        truncated = raw_str[:30000] + "...[truncated]" if len(raw_str) > 30000 else raw_str
        return f"{base_instruction}\n\n--- RAW CRAWL DATA ---\n{truncated}"

    return build_instruction


# ---------------------------------------------------------------------------
# Helper: inject socialData URLs from session state into instruction
# ---------------------------------------------------------------------------

def _with_social_urls(base_instruction: str):
    """Build dynamic instruction that injects socialData URLs from session state."""

    def build_instruction(context) -> str:
        social = getattr(context, "state", {}).get("socialData", {})
        social_str = social if isinstance(social, str) else json.dumps(social or {})
        return f"{base_instruction}\n\n--- SOCIAL PROFILE URLS ---\n{social_str}"

    return build_instruction


# ---------------------------------------------------------------------------
# Stage 1: SiteCrawlerAgent
# ---------------------------------------------------------------------------

site_crawler_agent = LlmAgent(
    name="SiteCrawlerAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=SITE_CRAWLER_INSTRUCTION,
    tools=[playwright_tool, crawl4ai_tool, crawl4ai_advanced_tool, crawl4ai_deep_tool],
    output_key="rawSiteData",
)

# ---------------------------------------------------------------------------
# Stage 2: Fan-out sub-agents
# ---------------------------------------------------------------------------

theme_agent = LlmAgent(
    name="ThemeAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_raw_data(THEME_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="themeData",
)

contact_agent = LlmAgent(
    name="ContactAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_raw_data(CONTACT_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="contactData",
)

social_media_agent = LlmAgent(
    name="SocialMediaAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_raw_data(SOCIAL_MEDIA_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="socialData",
)

menu_agent = LlmAgent(
    name="MenuAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_raw_data(MENU_AGENT_INSTRUCTION),
    tools=[playwright_tool, crawl4ai_advanced_tool, crawl4ai_deep_tool],
    output_key="menuData",
)

maps_agent = LlmAgent(
    name="MapsAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_raw_data(MAPS_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="mapsData",
)

competitor_agent = LlmAgent(
    name="CompetitorAgent",
    model=AgentModels.DEEP_ANALYST_MODEL,
    instruction=_with_raw_data(COMPETITOR_AGENT_INSTRUCTION),
    tools=[google_search_tool, crawl4ai_tool, crawl4ai_advanced_tool],
    output_key="competitorData",
)

# ---------------------------------------------------------------------------
# Stage 2: ParallelAgent fan-out
# ---------------------------------------------------------------------------

discovery_fan_out = ParallelAgent(
    name="DiscoveryFanOut",
    description="Runs 6 specialized discovery sub-agents concurrently, each processing raw crawl data.",
    sub_agents=[theme_agent, contact_agent, social_media_agent, menu_agent, maps_agent, competitor_agent],
)

# ---------------------------------------------------------------------------
# Stage 3: SocialProfilerAgent — crawls social URLs for metrics
# ---------------------------------------------------------------------------

social_profiler_agent = LlmAgent(
    name="SocialProfilerAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_social_urls(SOCIAL_PROFILER_INSTRUCTION),
    tools=[crawl4ai_advanced_tool],
    output_key="socialProfileMetrics",
)

# ---------------------------------------------------------------------------
# DiscoveryPipeline — exported orchestrator
# ---------------------------------------------------------------------------

discovery_pipeline = SequentialAgent(
    name="DiscoveryPipeline",
    description="Three-stage discovery: crawl site, fan out to 6 agents, then profile social accounts.",
    sub_agents=[site_crawler_agent, discovery_fan_out, social_profiler_agent],
)
