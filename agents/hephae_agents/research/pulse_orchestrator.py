"""PulseOrchestrator — factory for the weekly pulse ADK agent tree.

ADK agents can only have one parent. Since generate_pulse() may be called
multiple times in the same process, we use a factory function that creates
fresh agent instances each invocation.

Stage 3 uses dual-model synthesis: Gemini Flash + Claude (via LiteLlm) run
in parallel, then a deterministic InsightMerger combines their outputs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from google.adk.agents import (
    BaseAgent,
    LlmAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels, ThinkingPresets
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
from hephae_agents.research.weekly_pulse_agent import (
    _full_instruction,
    WEEKLY_PULSE_CORE_INSTRUCTION,
    _synthesis_instruction,
)
from hephae_agents.research.pulse_critique_agent import (
    CritiqueRouter,
    _critique_instruction,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 3: InsightMerger — deterministic merge of dual-model outputs
# ---------------------------------------------------------------------------


class InsightMerger(BaseAgent):
    """Deterministic merge of Gemini + Claude synthesis outputs.

    Reads geminiPulseOutput and claudePulseOutput from session state,
    merges localBriefing + insights, deduplicates, and writes combined
    result to pulseOutput.
    """

    name: str = "InsightMerger"
    description: str = "Merges dual-model synthesis outputs deterministically."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        gemini_raw = state.get("geminiPulseOutput", {})
        claude_raw = state.get("claudePulseOutput", {})

        # Parse if string
        gemini_output = self._parse_output(gemini_raw)
        claude_output = self._parse_output(claude_raw)

        # Merge local briefings
        merged_local = self._merge_local_briefing(
            gemini_output.get("localBriefing", {}),
            claude_output.get("localBriefing", {}),
        )

        # Merge insights
        gemini_insights = gemini_output.get("insights", [])
        claude_insights = claude_output.get("insights", [])
        merged_insights = self._merge_insights(gemini_insights, claude_insights)

        # Pick best headline (longer, more specific)
        gemini_headline = gemini_output.get("headline", "")
        claude_headline = claude_output.get("headline", "")
        headline = gemini_headline if len(gemini_headline) >= len(claude_headline) else claude_headline
        if not headline:
            zip_code = state.get("zipCode", "")
            business_type = state.get("businessType", "")
            week_of = state.get("weekOf", "")
            headline = f"{len(merged_insights)} insights for {zip_code} ({business_type}) — week of {week_of}"

        # Merge quickStats (prefer non-empty values)
        gemini_qs = gemini_output.get("quickStats", {})
        claude_qs = claude_output.get("quickStats", {})
        merged_qs = {
            "trendingSearches": gemini_qs.get("trendingSearches") or claude_qs.get("trendingSearches", []),
            "weatherOutlook": gemini_qs.get("weatherOutlook") or claude_qs.get("weatherOutlook", ""),
            "upcomingEvents": max(gemini_qs.get("upcomingEvents", 0), claude_qs.get("upcomingEvents", 0)),
            "priceAlerts": max(gemini_qs.get("priceAlerts", 0), claude_qs.get("priceAlerts", 0)),
        }

        combined = {
            "zipCode": state.get("zipCode", ""),
            "businessType": state.get("businessType", ""),
            "weekOf": state.get("weekOf", ""),
            "headline": headline,
            "localBriefing": merged_local,
            "insights": merged_insights,
            "quickStats": merged_qs,
        }

        logger.info(
            f"[InsightMerger] Gemini: {len(gemini_insights)} insights, "
            f"Claude: {len(claude_insights)} insights, "
            f"Combined: {len(merged_insights)} insights, "
            f"LocalEvents: {len(merged_local.get('thisWeekInTown', []))}, "
            f"Competitors: {len(merged_local.get('competitorWatch', []))}"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"pulseOutput": combined}),
        )

    def _parse_output(self, raw: Any) -> dict:
        """Parse raw output from state (may be str, dict, or Pydantic model)."""
        if not raw:
            return {}
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return {}
        if isinstance(raw, dict):
            return raw
        # Pydantic model
        if hasattr(raw, "model_dump"):
            return raw.model_dump()
        return {}

    def _merge_local_briefing(self, a: dict, b: dict) -> dict:
        """Merge localBriefing from two model outputs."""
        # Events: dedupe by venue+date
        events_a = a.get("thisWeekInTown", []) if isinstance(a, dict) else []
        events_b = b.get("thisWeekInTown", []) if isinstance(b, dict) else []
        seen_events: dict[str, dict] = {}
        for evt in events_a + events_b:
            if not isinstance(evt, dict):
                continue
            key = f"{evt.get('where', '').lower().strip()[:30]}|{evt.get('when', '').lower().strip()[:20]}"
            if key not in seen_events or len(evt.get("businessImpact", "")) > len(seen_events[key].get("businessImpact", "")):
                seen_events[key] = evt

        # Competitors: dedupe by business name
        comps_a = a.get("competitorWatch", []) if isinstance(a, dict) else []
        comps_b = b.get("competitorWatch", []) if isinstance(b, dict) else []
        seen_comps: dict[str, dict] = {}
        for comp in comps_a + comps_b:
            if not isinstance(comp, dict):
                continue
            key = comp.get("business", "").lower().strip()
            if key not in seen_comps or len(comp.get("observation", "")) > len(seen_comps[key].get("observation", "")):
                seen_comps[key] = comp

        # communityBuzz: pick the longer version
        buzz_a = a.get("communityBuzz", "") if isinstance(a, dict) else ""
        buzz_b = b.get("communityBuzz", "") if isinstance(b, dict) else ""
        community_buzz = buzz_a if len(buzz_a) >= len(buzz_b) else buzz_b

        # governmentWatch: pick the longer version
        gov_a = a.get("governmentWatch", "") if isinstance(a, dict) else ""
        gov_b = b.get("governmentWatch", "") if isinstance(b, dict) else ""
        government_watch = gov_a if len(gov_a) >= len(gov_b) else gov_b

        return {
            "thisWeekInTown": list(seen_events.values()),
            "competitorWatch": list(seen_comps.values()),
            "communityBuzz": community_buzz,
            "governmentWatch": government_watch,
        }

    def _merge_insights(self, gemini: list, claude: list) -> list[dict]:
        """Merge insights from both models, deduplicate, rank by score."""
        all_insights = list(gemini) + list(claude)

        # Deduplicate by title similarity
        seen_titles: dict[str, dict] = {}
        for ins in all_insights:
            if not isinstance(ins, dict):
                continue
            title = ins.get("title", "").lower().strip()
            key = title[:40]
            existing = seen_titles.get(key)
            if existing:
                if ins.get("impactScore", 0) > existing.get("impactScore", 0):
                    seen_titles[key] = ins
            else:
                seen_titles[key] = ins

        # Sort by impactScore descending, take top 8
        deduped = sorted(
            seen_titles.values(),
            key=lambda x: x.get("impactScore", 0),
            reverse=True,
        )[:8]

        # Re-rank
        for i, ins in enumerate(deduped, 1):
            ins["rank"] = i

        return deduped


def create_pulse_orchestrator() -> SequentialAgent:
    """Create a fresh PulseOrchestrator agent tree."""

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
        description="Parallel data layer: fetches all signals and runs LLM research fan-out simultaneously.",
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
        description="Parallel pre-processing: history summarizer, economist, and local scout run simultaneously.",
        sub_agents=[historian, economist, local_scout],
    )

    # ── Stage 3: Dual-Model Synthesis (Gemini + Claude via LiteLlm) ──
    gemini_synth = LlmAgent(
        name="GeminiSynthesis",
        model=AgentModels.SYNTHESIS_MODEL,
        generate_content_config=ThinkingPresets.HIGH,
        description="Gemini synthesis — generates pulse with local briefing.",
        instruction=_full_instruction,
        output_key="geminiPulseOutput",
        output_schema=WeeklyPulseOutput,
        on_model_error_callback=fallback_on_error,
    )
    claude_synth = LlmAgent(
        name="ClaudeSynthesis",
        model=LiteLlm(model=AgentModels.CLAUDE_SYNTHESIS_MODEL),
        description="Claude synthesis — generates pulse with local briefing.",
        instruction=_full_instruction,
        output_key="claudePulseOutput",
        output_schema=WeeklyPulseOutput,
        on_model_error_callback=fallback_on_error,
    )
    dual_synthesis = ParallelAgent(
        name="DualSynthesis",
        description="Parallel dual-model synthesis: Gemini and Claude generate pulse independently.",
        sub_agents=[gemini_synth, claude_synth],
    )
    synthesis_stage = SequentialAgent(
        name="SynthesisStage",
        sub_agents=[dual_synthesis, InsightMerger()],
    )

    # ── Stage 4: Critique Loop ─────────────────────────────────────
    critique = LlmAgent(
        name="PulseCritique",
        model=AgentModels.SYNTHESIS_MODEL,
        generate_content_config=ThinkingPresets.MEDIUM,
        description="Evaluates pulse insights for quality.",
        instruction=_critique_instruction,
        output_key="critiqueResult",
        output_schema=CritiqueResult,
        on_model_error_callback=fallback_on_error,
    )
    rewrite = LlmAgent(
        name="weekly_pulse_rewrite",
        model=AgentModels.SYNTHESIS_MODEL,
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
        description="5-stage weekly pulse pipeline with dual-model synthesis.",
        sub_agents=[data_gatherer, pre_synthesis, synthesis_stage, critique_loop],
    )
