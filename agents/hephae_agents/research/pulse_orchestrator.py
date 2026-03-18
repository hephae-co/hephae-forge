"""PulseOrchestrator — factory for the weekly pulse ADK agent tree.

ADK agents can only have one parent. Since generate_pulse() may be called
multiple times in the same process, we use a factory function that creates
fresh agent instances each invocation.

Usage:
    from hephae_agents.research.pulse_orchestrator import create_pulse_orchestrator
    orchestrator = create_pulse_orchestrator()
    # Use with ADK Runner
"""

from __future__ import annotations

from google.adk.agents import (
    LlmAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.events.event_actions import EventActions
from google.adk.tools import google_search

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_db.schemas import CritiqueResult, WeeklyPulseOutput

# Import instruction builders (stateless functions, safe to reuse)
from hephae_agents.research.pulse_data_gatherer import (
    BaseLayerFetcher,
    _social_pulse_instruction,
    _local_catalyst_instruction,
)
from hephae_agents.research.pulse_domain_experts import (
    _historian_instruction,
    _economist_instruction,
    _local_scout_instruction,
)
from hephae_agents.research.weekly_pulse_agent import _full_instruction
from hephae_agents.research.pulse_critique_agent import (
    CritiqueRouter,
    _critique_instruction,
)


def create_pulse_orchestrator() -> SequentialAgent:
    """Create a fresh PulseOrchestrator agent tree.

    Returns a new SequentialAgent with all sub-agents freshly instantiated,
    avoiding the "already has a parent" error on repeated calls.
    """

    # ── Stage 1: DataGatherer ──────────────────────────────────────
    social_pulse = LlmAgent(
        name="SocialPulseResearch",
        model=AgentModels.PRIMARY_MODEL,
        description="Scans social media for community sentiment.",
        instruction=_social_pulse_instruction,
        tools=[google_search],
        output_key="socialPulse",
        on_model_error_callback=fallback_on_error,
    )
    local_catalyst = LlmAgent(
        name="LocalCatalystResearch",
        model=AgentModels.PRIMARY_MODEL,
        description="Researches forward-looking local government signals.",
        instruction=_local_catalyst_instruction,
        tools=[google_search_tool, crawl4ai_advanced_tool],
        output_key="localCatalysts",
        on_model_error_callback=fallback_on_error,
    )
    research_fan_out = ParallelAgent(
        name="ResearchFanOut",
        sub_agents=[social_pulse, local_catalyst],
    )
    data_gatherer = ParallelAgent(
        name="DataGatherer",
        sub_agents=[BaseLayerFetcher(), research_fan_out],
    )

    # ── Stage 2: PreSynthesis ──────────────────────────────────────
    historian = LlmAgent(
        name="PulseHistorySummarizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Analyzes 12-week pulse history for longitudinal trends.",
        instruction=_historian_instruction,
        output_key="trendNarrative",
        on_model_error_callback=fallback_on_error,
    )
    economist = LlmAgent(
        name="EconomistAgent",
        model=AgentModels.PRIMARY_MODEL,
        description="Distills economic and demographic signals into a macro report.",
        instruction=_economist_instruction,
        output_key="macroReport",
        on_model_error_callback=fallback_on_error,
    )
    local_scout = LlmAgent(
        name="LocalScoutAgent",
        model=AgentModels.PRIMARY_MODEL,
        description="Distills local weather, news, catalysts, and social signals.",
        instruction=_local_scout_instruction,
        output_key="localReport",
        on_model_error_callback=fallback_on_error,
    )
    pre_synthesis = ParallelAgent(
        name="PreSynthesis",
        sub_agents=[historian, economist, local_scout],
    )

    # ── Stage 3: Synthesis ─────────────────────────────────────────
    synthesis = LlmAgent(
        name="weekly_pulse",
        model=AgentModels.PRIMARY_MODEL,
        generate_content_config=ThinkingPresets.DEEP,
        description="Synthesizes expert reports into weekly insight cards.",
        instruction=_full_instruction,
        output_key="pulseOutput",
        output_schema=WeeklyPulseOutput,
        on_model_error_callback=fallback_on_error,
    )

    # ── Stage 4: Critique Loop ─────────────────────────────────────
    critique = LlmAgent(
        name="PulseCritique",
        model=AgentModels.PRIMARY_MODEL,
        generate_content_config=ThinkingPresets.MEDIUM,
        description="Evaluates pulse insights for quality.",
        instruction=_critique_instruction,
        output_key="critiqueResult",
        output_schema=CritiqueResult,
        on_model_error_callback=fallback_on_error,
    )
    # Rewrite agent (same config as synthesis, reads rewriteFeedback)
    rewrite = LlmAgent(
        name="weekly_pulse_rewrite",
        model=AgentModels.PRIMARY_MODEL,
        generate_content_config=ThinkingPresets.DEEP,
        description="Rewrites failing insights based on critique feedback.",
        instruction=_full_instruction,
        output_key="pulseOutput",
        output_schema=WeeklyPulseOutput,
        on_model_error_callback=fallback_on_error,
    )
    critique_sequence = SequentialAgent(
        name="CritiqueThenRewrite",
        sub_agents=[critique, CritiqueRouter(), rewrite],
    )
    critique_loop = LoopAgent(
        name="CritiqueLoop",
        sub_agents=[critique_sequence],
        max_iterations=2,
    )

    # ── Wire all stages ────────────────────────────────────────────
    return SequentialAgent(
        name="PulseOrchestrator",
        description="5-stage weekly pulse pipeline.",
        sub_agents=[data_gatherer, pre_synthesis, synthesis, critique_loop],
    )
