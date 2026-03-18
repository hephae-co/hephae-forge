"""Stage 1: DataGatherer — deterministic data fetching + LLM research fan-out.

Architecture:
  DataGatherer (ParallelAgent)
  ├─ BaseLayerFetcher (custom BaseAgent — no LLM, deterministic)
  │   Calls all API/BQ fetch tools in parallel, writes to session.state
  ├─ ResearchFanOut (ParallelAgent)
  │   ├─ SocialPulseResearch (LlmAgent + google_search)
  │   └─ LocalCatalystResearch (LlmAgent + google_search + crawl4ai)

BaseLayerFetcher also computes pre_computed_impact and matches playbooks
AFTER fetching signals, writing both to session.state for Stage 3.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.tools import google_search

from hephae_api.config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_agents.research.social_pulse import SOCIAL_PULSE_INSTRUCTION
from hephae_agents.research.local_catalyst import LOCAL_CATALYST_INSTRUCTION

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BaseLayerFetcher — deterministic, no LLM
# ---------------------------------------------------------------------------


class BaseLayerFetcher(BaseAgent):
    """Fetches all API/BQ data sources in parallel without LLM.

    Writes raw signals, pre-computed impact, and matched playbooks
    to session.state for downstream stages.
    """

    name: str = "BaseLayerFetcher"
    description: str = "Deterministic parallel data fetcher — no LLM, just tools."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        zip_code = state.get("zipCode", "")
        business_type = state.get("businessType", "")
        city = state.get("city", "")
        st = state.get("state", "")
        county = state.get("county", "")
        latitude = state.get("latitude", 0.0)
        longitude = state.get("longitude", 0.0)
        dma_name = state.get("dmaName", "")

        logger.info(f"[BaseLayerFetcher] Fetching signals for {zip_code} ({business_type})")

        # Fetch all signals via cache-through wrappers
        from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_all_signals

        signals = await fetch_all_signals(
            zip_code=zip_code,
            business_type=business_type,
            city=city,
            state=st,
            county=county,
            latitude=latitude,
            longitude=longitude,
            dma_name=dma_name,
        )

        # Load zip code research if available
        try:
            from hephae_db.firestore.research import get_zipcode_report
            zip_data = await get_zipcode_report(zip_code)
            if zip_data:
                signals["zipReport"] = zip_data.get("report", {})
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] Zip research load failed: {e}")

        # Compute pre-computed impact multipliers (Python math, not LLM)
        from hephae_api.workflows.orchestrators.pulse_playbooks import (
            compute_impact_multipliers,
            match_playbooks,
        )

        pre_computed = compute_impact_multipliers(signals)
        matched_playbooks = match_playbooks(pre_computed, signals, business_type)

        # Write everything to session state
        state_delta = {
            "rawSignals": signals,
            "signalsUsed": [k for k, v in signals.items() if v],
            "preComputedImpact": pre_computed,
            "matchedPlaybooks": matched_playbooks,
        }

        # Update session state
        for key, value in state_delta.items():
            ctx.session.state[key] = value

        logger.info(
            f"[BaseLayerFetcher] Done: {len(signals)} signals, "
            f"{len(pre_computed)} impact vars, {len(matched_playbooks)} playbooks"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
        )


# ---------------------------------------------------------------------------
# Research sub-agents (LLM-powered, parallel)
# ---------------------------------------------------------------------------


def _social_pulse_instruction(ctx) -> str:
    """Inject location from session state into SocialPulse instruction."""
    state = getattr(ctx, "state", {})
    city = state.get("city", "unknown")
    st = state.get("state", "")
    zip_code = state.get("zipCode", "")
    return (
        f"{SOCIAL_PULSE_INSTRUCTION}\n\n"
        f"TOWN/CITY: {city}\nSTATE: {st}\nZIP CODE: {zip_code}\n"
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"
    )


def _local_catalyst_instruction(ctx) -> str:
    """Inject location from session state into LocalCatalyst instruction."""
    state = getattr(ctx, "state", {})
    city = state.get("city", "unknown")
    st = state.get("state", "")
    biz_type = state.get("businessType", "unknown")
    return (
        f"{LOCAL_CATALYST_INSTRUCTION}\n\n"
        f"TOWN/CITY: {city}\nSTATE: {st}\nBUSINESS TYPE: {biz_type}\n"
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"
    )


_social_pulse_research = LlmAgent(
    name="SocialPulseResearch",
    model=AgentModels.PRIMARY_MODEL,
    description="Scans social media for community sentiment.",
    instruction=_social_pulse_instruction,
    tools=[google_search],
    output_key="socialPulse",
    on_model_error_callback=fallback_on_error,
)

_local_catalyst_research = LlmAgent(
    name="LocalCatalystResearch",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches forward-looking local government signals.",
    instruction=_local_catalyst_instruction,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    output_key="localCatalysts",
    on_model_error_callback=fallback_on_error,
)

_research_fan_out = ParallelAgent(
    name="ResearchFanOut",
    sub_agents=[_social_pulse_research, _local_catalyst_research],
)


# ---------------------------------------------------------------------------
# Stage 1: DataGatherer — runs fetcher + research in parallel
# ---------------------------------------------------------------------------

data_gatherer = ParallelAgent(
    name="DataGatherer",
    sub_agents=[BaseLayerFetcher(), _research_fan_out],
)
