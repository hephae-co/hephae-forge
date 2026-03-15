"""
DiscoveryPipeline — six-stage discovery:
  Stage 1: SiteCrawlerAgent crawls the business URL once -> rawSiteData
  Stage 1.5: EntityMatcherAgent validates the crawled site matches the target business -> entityMatchResult
  Stage 2: DiscoveryFanOut fans out to 9 specialized agents (gated — skips agents whose data is already found)
  Stage 3: SocialProfilerAgent researches social profiles via google_search + crawl4ai -> socialProfileMetrics
  Stage 4: DiscoveryReviewerAgent validates all URLs and corrects invalid ones -> reviewerData

Uses Google ADK Python SDK (LlmAgent, ParallelAgent, SequentialAgent).
"""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_db.schemas.agent_outputs import (
    EntityMatchOutput,
)
from hephae_agents.shared_tools import (
    google_search_tool,
    playwright_tool,
    crawl4ai_tool,
    crawl4ai_advanced_tool,
    crawl4ai_deep_tool,
    validate_url_tool,
)
from hephae_agents.discovery.prompts import (
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
    ENTITY_MATCHER_INSTRUCTION,
    CHALLENGES_AGENT_INSTRUCTION,
)

logger = logging.getLogger(__name__)


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
# Stage 1.5: EntityMatcherAgent — validates site belongs to target business (P0.3)
# ---------------------------------------------------------------------------

entity_matcher_agent = LlmAgent(
    name="EntityMatcherAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(ENTITY_MATCHER_INSTRUCTION),
    tools=[],  # Pure analysis — no tools needed
    output_key="entityMatchResult",
    output_schema=EntityMatchOutput,
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
    # output_schema incompatible with tools — Gemini rejects response_schema + tool use
    on_model_error_callback=fallback_on_error,
)

contact_agent = LlmAgent(
    name="ContactAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(CONTACT_AGENT_INSTRUCTION),
    tools=[google_search_tool, playwright_tool],
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
    tools=[google_search_tool, playwright_tool, crawl4ai_advanced_tool, crawl4ai_deep_tool],
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
# P0.2: ChallengesAgent — dedicated pain points researcher
# ---------------------------------------------------------------------------

challenges_agent = LlmAgent(
    name="ChallengesAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_raw_data(CHALLENGES_AGENT_INSTRUCTION),
    tools=[google_search_tool],
    output_key="challengesData",
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# P1.2: Targeted crawl instructions — inject discovered page URLs
# ---------------------------------------------------------------------------

def _with_raw_data_and_contact_pages(base_instruction: str):
    """Inject rawSiteData + discovered contact page URLs into instruction."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        raw = state.get("rawSiteData", {})
        raw_str = raw if isinstance(raw, str) else json.dumps(raw or {})
        truncated = raw_str[:30000] + "...[truncated]" if len(raw_str) > 30000 else raw_str

        # Extract contact page URLs and deterministic contact results from Stage 1
        contact_pages = []
        det_contact = {}
        if isinstance(raw, dict):
            contact_pages = raw.get("contactPages", [])
            det_contact = raw.get("deterministicContact", {})
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                contact_pages = parsed.get("contactPages", [])
                det_contact = parsed.get("deterministicContact", {})
            except (json.JSONDecodeError, ValueError):
                pass

        hints = ""
        if det_contact.get("email"):
            hints += f"\n\nDETERMINISTIC EXTRACTION ALREADY FOUND EMAIL: {det_contact['email']}"
            hints += "\nYou can skip email extraction steps and focus on verifying this email and finding other contact info."
        if det_contact.get("phone"):
            hints += f"\nDETERMINISTIC EXTRACTION ALREADY FOUND PHONE: {det_contact['phone']}"
        if contact_pages:
            hints += f"\n\nDISCOVERED CONTACT PAGES (crawl these first if email is missing): {json.dumps(contact_pages)}"

        return f"{base_instruction}{hints}\n\n--- RAW CRAWL DATA ---\n{truncated}"

    return build_instruction


def _with_raw_data_and_menu_hints(base_instruction: str):
    """Inject rawSiteData + discovered pages for targeted menu search."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        raw = state.get("rawSiteData", {})
        raw_str = raw if isinstance(raw, str) else json.dumps(raw or {})
        truncated = raw_str[:30000] + "...[truncated]" if len(raw_str) > 30000 else raw_str

        # Extract discovered pages from deep crawl
        discovered = []
        if isinstance(raw, dict):
            discovered = raw.get("discoveredPages", []) or []
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                discovered = parsed.get("discoveredPages", []) or []
            except (json.JSONDecodeError, ValueError):
                pass

        hints = ""
        if discovered:
            # Filter for menu-like pages
            menu_pages = [
                p for p in discovered
                if isinstance(p, (str, dict)) and any(
                    kw in (p if isinstance(p, str) else json.dumps(p)).lower()
                    for kw in ("menu", "food", "dining", "eat", "drink", "lunch", "dinner", "catering")
                )
            ]
            if menu_pages:
                hints += f"\n\nDISCOVERED MENU-LIKE PAGES (crawl these first): {json.dumps(menu_pages[:5])}"

        return f"{base_instruction}{hints}\n\n--- RAW CRAWL DATA ---\n{truncated}"

    return build_instruction


# ---------------------------------------------------------------------------
# P2.1: Stage gating — skip agents if data already found in Stage 1
# ---------------------------------------------------------------------------

def _should_skip_contact(context) -> bool:
    """Skip ContactAgent if deterministic extraction already found both email and phone."""
    raw = getattr(context, "state", {}).get("rawSiteData", {})
    det = {}
    if isinstance(raw, dict):
        det = raw.get("deterministicContact", {})
    elif isinstance(raw, str):
        try:
            det = json.loads(raw).get("deterministicContact", {})
        except (json.JSONDecodeError, ValueError):
            pass
    return bool(det.get("email") and det.get("phone"))


def _should_skip_social(context) -> bool:
    """Skip SocialMediaAgent if crawl already found 3+ social links."""
    raw = getattr(context, "state", {}).get("rawSiteData", {})
    sa = {}
    if isinstance(raw, dict):
        sa = raw.get("socialAnchors", {})
    elif isinstance(raw, str):
        try:
            sa = json.loads(raw).get("socialAnchors", {})
        except (json.JSONDecodeError, ValueError):
            pass
    found = sum(1 for v in sa.values() if v)
    return found >= 3


def _should_skip_menu(context) -> bool:
    """Skip MenuAgent if crawl already found a menu URL."""
    raw = getattr(context, "state", {}).get("rawSiteData", {})
    if isinstance(raw, dict):
        return bool(raw.get("menuUrl"))
    if isinstance(raw, str):
        try:
            return bool(json.loads(raw).get("menuUrl"))
        except (json.JSONDecodeError, ValueError):
            pass
    return False


def _gate_agent(agent: LlmAgent, skip_fn, output_key: str):
    """Wrap an agent with a before_agent_callback that skips it if data exists.

    When skipped, we populate the output_key with the data from Stage 1
    so downstream agents still have it available.
    """
    original_instruction = agent.instruction

    def _gated_instruction(context) -> str:
        if skip_fn(context):
            # Populate from Stage 1 data so downstream still has it
            raw = getattr(context, "state", {}).get("rawSiteData", {})
            data = raw if isinstance(raw, dict) else {}
            if output_key == "contactData":
                det = data.get("deterministicContact", {})
                logger.info("[StageGating] Skipping ContactAgent — deterministic data available")
                # Return a minimal instruction that tells the agent to just output what we found
                return (
                    "The contact information was already extracted deterministically. "
                    f"Return this JSON exactly: {json.dumps({'phone': det.get('phone'), 'email': det.get('email'), 'emailStatus': 'found' if det.get('email') else 'not_found', 'contactFormUrl': None, 'contactFormStatus': 'not_found'})}"
                )
            elif output_key == "socialData":
                sa = data.get("socialAnchors", {})
                dp = data.get("deliveryPlatforms", {})
                logger.info("[StageGating] Skipping SocialMediaAgent — crawl data sufficient")
                merged = {**sa, **dp}
                return f"Social data was already found in the crawl. Return this JSON exactly: {json.dumps(merged)}"
            elif output_key == "menuData":
                menu_url = data.get("menuUrl")
                dp = data.get("deliveryPlatforms", {})
                logger.info("[StageGating] Skipping MenuAgent — menu URL already found")
                return f"Menu URL was already found. Return this JSON exactly: {json.dumps({'menuUrl': menu_url, **{k: dp.get(k) for k in ['grubhub', 'doordash', 'ubereats', 'seamless', 'toasttab']}})}"
        # Not skipped — use the original instruction
        if callable(original_instruction):
            return original_instruction(context)
        return original_instruction

    agent.instruction = _gated_instruction
    return agent


# Apply P1.2 targeted instructions to ContactAgent and MenuAgent
contact_agent.instruction = _with_raw_data_and_contact_pages(CONTACT_AGENT_INSTRUCTION)
menu_agent.instruction = _with_raw_data_and_menu_hints(MENU_AGENT_INSTRUCTION)

# Apply P2.1 stage gating
_gate_agent(contact_agent, _should_skip_contact, "contactData")
_gate_agent(social_media_agent, _should_skip_social, "socialData")
_gate_agent(menu_agent, _should_skip_menu, "menuData")


# ---------------------------------------------------------------------------
# Stage 2: ParallelAgent fan-out (now 9 agents with ChallengesAgent)
# ---------------------------------------------------------------------------

discovery_fan_out = ParallelAgent(
    name="DiscoveryFanOut",
    description="Runs 9 specialized discovery sub-agents concurrently, each processing raw crawl data.",
    sub_agents=[theme_agent, contact_agent, social_media_agent, menu_agent, maps_agent, competitor_agent, news_agent, business_overview_agent, challenges_agent],
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
            "aiOverview", "challengesData",
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
# Exported pipelines — split for early abort on entity mismatch
# ---------------------------------------------------------------------------

# Phase 1: Crawl + entity validation (runs first; runner checks result before continuing)
discovery_phase1 = SequentialAgent(
    name="DiscoveryPhase1",
    description="Crawl site and validate entity match.",
    sub_agents=[site_crawler_agent, entity_matcher_agent],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

# Phase 2: Full research (only runs if entity match passes)
discovery_phase2 = SequentialAgent(
    name="DiscoveryPhase2",
    description="Fan out to 9 agents (gated), profile social accounts, then validate all data.",
    sub_agents=[discovery_fan_out, social_profiler_agent, discovery_reviewer_agent],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)

# Combined pipeline (nests phase1 + phase2 — for evals/integration tests that run the full pipeline)
discovery_pipeline = SequentialAgent(
    name="DiscoveryPipeline",
    description="Six-stage discovery: crawl site, entity match, fan out to 9 agents (gated), profile social accounts, then validate all data.",
    sub_agents=[discovery_phase1, discovery_phase2],
)
