"""
DiscoveryPipeline — four-stage discovery:
  Stage 1: SiteCrawlerAgent crawls the business URL once -> rawSiteData
  Stage 2: DiscoveryFanOut fans out to 8 specialized agents reading rawSiteData
  Stage 3: SocialProfilerAgent researches social profiles via google_search + crawl4ai -> socialProfileMetrics
  Stage 4: DiscoveryReviewerAgent validates all URLs and corrects invalid ones -> reviewerData

Uses Google ADK Python SDK (LlmAgent, ParallelAgent, SequentialAgent).
"""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from backend.config import AgentModels, ThinkingPresets
from backend.lib.model_fallback import fallback_on_error
from backend.agents.shared_tools import (
    google_search_tool,
    playwright_tool,
    crawl4ai_tool,
    crawl4ai_advanced_tool,
    crawl4ai_deep_tool,
    validate_url_tool,
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
    BUSINESS_OVERVIEW_INSTRUCTION,
    NEWS_AGENT_INSTRUCTION,
    DISCOVERY_REVIEWER_INSTRUCTION,
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
    model=AgentModels.PRIMARY_MODEL,
    instruction=SITE_CRAWLER_INSTRUCTION,
    tools=[playwright_tool, crawl4ai_tool, crawl4ai_advanced_tool, crawl4ai_deep_tool],
    output_key="rawSiteData",
    on_model_error_callback=fallback_on_error,
)

# ---------------------------------------------------------------------------
# Stage 2: Fan-out sub-agents
# ---------------------------------------------------------------------------

theme_agent = LlmAgent(
    name="ThemeAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(THEME_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="themeData",
    on_model_error_callback=fallback_on_error,
)

contact_agent = LlmAgent(
    name="ContactAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(CONTACT_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="contactData",
    on_model_error_callback=fallback_on_error,
)

social_media_agent = LlmAgent(
    name="SocialMediaAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(SOCIAL_MEDIA_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="socialData",
    on_model_error_callback=fallback_on_error,
)

menu_agent = LlmAgent(
    name="MenuAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(MENU_AGENT_INSTRUCTION),
    tools=[playwright_tool, crawl4ai_advanced_tool, crawl4ai_deep_tool],
    output_key="menuData",
    on_model_error_callback=fallback_on_error,
)

maps_agent = LlmAgent(
    name="MapsAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(MAPS_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="mapsData",
    on_model_error_callback=fallback_on_error,
)

competitor_agent = LlmAgent(
    name="CompetitorAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    instruction=_with_raw_data(COMPETITOR_AGENT_INSTRUCTION),
    tools=[google_search_tool, crawl4ai_tool, crawl4ai_advanced_tool],
    output_key="competitorData",
    on_model_error_callback=fallback_on_error,
)

news_agent = LlmAgent(
    name="NewsAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(NEWS_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="newsData",
    on_model_error_callback=fallback_on_error,
)

business_overview_agent = LlmAgent(
    name="BusinessOverviewAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(BUSINESS_OVERVIEW_INSTRUCTION),
    tools=[google_search_tool],
    output_key="aiOverview",
    on_model_error_callback=fallback_on_error,
)

# ---------------------------------------------------------------------------
# Stage 2: ParallelAgent fan-out
# ---------------------------------------------------------------------------

discovery_fan_out = ParallelAgent(
    name="DiscoveryFanOut",
    description="Runs 8 specialized discovery sub-agents concurrently, each processing raw crawl data.",
    sub_agents=[theme_agent, contact_agent, social_media_agent, menu_agent, maps_agent, competitor_agent, news_agent, business_overview_agent],
)

# ---------------------------------------------------------------------------
# Stage 3: SocialProfilerAgent — crawls social URLs for metrics
# ---------------------------------------------------------------------------

social_profiler_agent = LlmAgent(
    name="SocialProfilerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_social_urls(SOCIAL_PROFILER_INSTRUCTION),
    tools=[google_search_tool, crawl4ai_advanced_tool],
    output_key="socialProfileMetrics",
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Helper: inject all discovery data from session state into instruction
# ---------------------------------------------------------------------------

def _with_all_discovery_data(base_instruction: str):
    """Build dynamic instruction that injects ALL prior stage data from session state."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        data_keys = [
            "themeData", "contactData", "socialData", "menuData",
            "mapsData", "competitorData", "newsData", "socialProfileMetrics",
            "aiOverview",
        ]
        all_data = {}
        for key in data_keys:
            val = state.get(key)
            if val is not None:
                if isinstance(val, str):
                    all_data[key] = val[:10000]
                else:
                    serialized = json.dumps(val)
                    all_data[key] = serialized[:10000]
        data_str = json.dumps(all_data, indent=2)
        if len(data_str) > 40000:
            data_str = data_str[:40000] + "\n...[truncated]"
        return f"{base_instruction}\n\n--- ALL DISCOVERY DATA ---\n{data_str}"

    return build_instruction


# ---------------------------------------------------------------------------
# Stage 4: DiscoveryReviewerAgent — validates all URLs and cross-references
# ---------------------------------------------------------------------------

discovery_reviewer_agent = LlmAgent(
    name="DiscoveryReviewerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_all_discovery_data(DISCOVERY_REVIEWER_INSTRUCTION),
    tools=[validate_url_tool, google_search_tool],
    output_key="reviewerData",
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# DiscoveryPipeline — exported orchestrator
# ---------------------------------------------------------------------------

discovery_pipeline = SequentialAgent(
    name="DiscoveryPipeline",
    description="Four-stage discovery: crawl site, fan out to 8 agents, profile social accounts, then validate all data.",
    sub_agents=[site_crawler_agent, discovery_fan_out, social_profiler_agent, discovery_reviewer_agent],
)
