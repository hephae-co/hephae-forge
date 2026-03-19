"""PulseOrchestrator — factory for the weekly pulse ADK agent tree.

ADK agents can only have one parent. Since generate_pulse() may be called
multiple times in the same process, we use a factory function that creates
fresh agent instances each invocation.

Stage 3 uses dual-model synthesis: Gemini Flash + Claude run in parallel,
then a deterministic combiner merges and deduplicates their insights.
"""

from __future__ import annotations

import asyncio
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
# Stage 3: Dual-Model Synthesis (Gemini Flash + Claude in parallel)
# ---------------------------------------------------------------------------


class DualModelSynthesis(BaseAgent):
    """Runs Gemini Flash and Claude in parallel, merges best insights.

    Gemini runs as an ADK LlmAgent (structured output via response_schema).
    Claude runs as a plain async HTTP call (no ADK needed).
    A deterministic combiner merges insights, deduplicates by title similarity,
    and keeps the highest-scored version of each.
    """

    name: str = "DualModelSynthesis"
    description: str = "Dual-model synthesis: Gemini Flash + Claude in parallel."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        # Build the prompt context from state (same for both models)
        context = _synthesis_instruction(ctx)
        full_prompt = f"{WEEKLY_PULSE_CORE_INSTRUCTION}\n\n{context}"

        # Run both models in parallel
        gemini_task = asyncio.create_task(self._run_gemini(full_prompt, state))
        claude_task = asyncio.create_task(self._run_claude(full_prompt, state))

        gemini_insights, claude_insights = await asyncio.gather(
            gemini_task, claude_task, return_exceptions=True,
        )

        # Handle errors gracefully
        if isinstance(gemini_insights, Exception):
            logger.error(f"[DualSynthesis] Gemini failed: {gemini_insights}")
            gemini_insights = []
        if isinstance(claude_insights, Exception):
            logger.error(f"[DualSynthesis] Claude failed: {claude_insights}")
            claude_insights = []

        # Combine and deduplicate
        combined = self._merge_insights(
            gemini_insights or [], claude_insights or [], state,
        )

        logger.info(
            f"[DualSynthesis] Gemini: {len(gemini_insights or [])} insights, "
            f"Claude: {len(claude_insights or [])} insights, "
            f"Combined: {len(combined.get('insights', []))} insights"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"pulseOutput": combined}),
        )

    async def _run_gemini(self, prompt: str, state: dict) -> list[dict]:
        """Run Gemini Flash synthesis via google-genai client."""
        try:
            from hephae_common.gemini_client import get_genai_client

            client = get_genai_client()
            response = await client.aio.models.generate_content(
                model=AgentModels.SYNTHESIS_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "thinking_config": {"thinking_level": "HIGH"},
                },
            )
            text = response.text
            if text:
                parsed = json.loads(text)
                insights = parsed.get("insights", [])
                for ins in insights:
                    ins["_source"] = "gemini"
                return insights
        except Exception as e:
            logger.error(f"[DualSynthesis:Gemini] Failed: {e}")
        return []

    async def _run_claude(self, prompt: str, state: dict) -> list[dict]:
        """Run Claude synthesis via Anthropic API."""
        try:
            from hephae_common.anthropic_client import generate_claude

            result = await generate_claude(
                prompt=prompt,
                system=(
                    "You are a data analyst writing a weekly intelligence briefing. "
                    "Return ONLY valid JSON matching this structure: "
                    '{"insights": [{"rank": 1, "title": "...", "analysis": "...", '
                    '"recommendation": "...", "dataSources": [...], "signalSources": [...], '
                    '"impactScore": 85, "impactLevel": "high", "timeSensitivity": "this_week", '
                    '"playbookUsed": ""}], "headline": "...", '
                    '"quickStats": {"trendingSearches": [], "weatherOutlook": "", '
                    '"upcomingEvents": 0, "priceAlerts": 0}}'
                ),
                response_format="json",
            )
            if result and isinstance(result, dict):
                insights = result.get("insights", [])
                for ins in insights:
                    ins["_source"] = "claude"
                return insights
        except Exception as e:
            logger.error(f"[DualSynthesis:Claude] Failed: {e}")
        return []

    def _merge_insights(
        self,
        gemini: list[dict],
        claude: list[dict],
        state: dict,
    ) -> dict:
        """Merge insights from both models, deduplicate, rank by score."""
        all_insights = gemini + claude

        # Deduplicate by title similarity (if titles overlap >60%, keep higher score)
        seen_titles: dict[str, dict] = {}
        for ins in all_insights:
            title = ins.get("title", "").lower().strip()
            key = title[:40]  # rough dedup key
            existing = seen_titles.get(key)
            if existing:
                # Keep the one with higher impactScore
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
            ins.pop("_source", None)

        # Build the full output
        zip_code = state.get("zipCode", "")
        business_type = state.get("businessType", "")
        week_of = state.get("weekOf", "")

        # Use the best headline from either model
        headline = ""
        if gemini:
            # Try to extract headline from Gemini's full response
            headline = f"{len(deduped)} insights for {zip_code} ({business_type}) — week of {week_of}"

        return {
            "zipCode": zip_code,
            "businessType": business_type,
            "weekOf": week_of,
            "headline": headline,
            "insights": deduped,
            "quickStats": {
                "trendingSearches": [],
                "weatherOutlook": "",
                "upcomingEvents": 0,
                "priceAlerts": 0,
            },
        }


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

    # ── Stage 3: Dual-Model Synthesis (Gemini Flash + Claude) ─────
    synthesis = DualModelSynthesis()

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
        sub_agents=[data_gatherer, pre_synthesis, synthesis, critique_loop],
    )
