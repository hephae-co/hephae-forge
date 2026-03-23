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

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions

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

        # Read zipcode profile if available (for downstream source-aware fetching)
        try:
            from hephae_db.firestore.zipcode_profiles import get_zipcode_profile
            profile = await get_zipcode_profile(zip_code)
            if profile:
                state["zipcodeProfile"] = profile
                logger.info(
                    f"[BaseLayerFetcher] Loaded profile for {zip_code}: "
                    f"{profile.get('confirmedSources', 0)} confirmed sources"
                )
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] Zipcode profile load failed: {e}")

        # ── Two-layer signal fetch ──────────────────────────────────
        # Layer 1: Try loading pre-computed industry pulse (national data)
        # Layer 2: Fetch local signals for this zip code
        # Fallback: If no industry pulse exists, fetch everything directly

        from hephae_api.workflows.orchestrators.pulse_fetch_tools import (
            fetch_local_signals,
            fetch_national_signals,
        )
        from hephae_api.workflows.orchestrators.pulse_playbooks import (
            compute_impact_multipliers,
            match_playbooks,
        )

        week_of = state.get("weekOf", "")
        industry_pulse = None
        industry_trend_summary = ""

        # Try loading the industry pulse (pre-computed by industry cron)
        try:
            from hephae_api.workflows.orchestrators.industries import resolve
            industry = resolve(business_type)
            from hephae_db.firestore.industry_pulse import get_industry_pulse
            industry_pulse = await get_industry_pulse(industry.id, week_of)
            if industry_pulse:
                logger.info(
                    f"[BaseLayerFetcher] Loaded industry pulse {industry.id}-{week_of} "
                    f"({len(industry_pulse.get('signalsUsed', []))} signals)"
                )
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] Industry pulse load failed: {e}")

        # Load tech intelligence (pre-computed by tech intelligence cron)
        tech_intelligence = {}
        try:
            from hephae_db.firestore.tech_intelligence import get_tech_intelligence
            industry_id = resolve(business_type).id if business_type else "restaurant"
            tech_profile = await get_tech_intelligence(industry_id, week_of)
            if tech_profile:
                tech_intelligence = {
                    "weeklyHighlight": tech_profile.get("weeklyHighlight"),
                    "aiOpportunities": tech_profile.get("aiOpportunities", [])[:3],
                    "platformUpdates": {
                        cat: info.get("recentUpdate", "")
                        for cat, info in tech_profile.get("platforms", {}).items()
                        if isinstance(info, dict) and info.get("recentUpdate")
                    },
                    "emergingTrends": tech_profile.get("emergingTrends", [])[:2],
                }
                logger.info(
                    f"[BaseLayerFetcher] Loaded tech intelligence for {industry_id}-{week_of}: "
                    f"{len(tech_intelligence.get('aiOpportunities', []))} AI opportunities"
                )
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] Tech intelligence load failed: {e}")

        # Fetch local signals (always — these are zip-specific)
        local_signals = await fetch_local_signals(
            zip_code=zip_code,
            business_type=business_type,
            city=city,
            state=st,
            county=county,
            latitude=latitude,
            longitude=longitude,
            dma_name=dma_name,
        )

        if industry_pulse:
            # Use pre-computed national data from industry pulse
            national_signals = industry_pulse.get("nationalSignals", {})
            national_impact = industry_pulse.get("nationalImpact", {})
            national_playbooks = industry_pulse.get("nationalPlaybooks", [])
            industry_trend_summary = industry_pulse.get("trendSummary", "")
            signals = {**national_signals, **local_signals}
            # Compute local impact and merge with national
            local_impact = compute_impact_multipliers(local_signals)
            pre_computed = {**national_impact, **local_impact}
            # Dedupe playbooks by name
            seen = {p.get("name") for p in national_playbooks}
            local_playbooks = [
                p for p in match_playbooks(local_impact, local_signals, business_type)
                if p.get("name") not in seen
            ]
            matched_playbooks = national_playbooks + local_playbooks
        else:
            # Fallback: fetch national signals directly (existing behavior)
            logger.info(f"[BaseLayerFetcher] No industry pulse — fetching all signals directly")
            national_signals = await fetch_national_signals(business_type, st)
            signals = {**national_signals, **local_signals}
            pre_computed = compute_impact_multipliers(signals)
            matched_playbooks = match_playbooks(pre_computed, signals, business_type)

        # Load zip code research if available
        try:
            from hephae_db.firestore.research import get_zipcode_report
            zip_data = await get_zipcode_report(zip_code)
            if zip_data:
                signals["zipReport"] = zip_data.get("report", {})
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] Zip research load failed: {e}")

        # Resolve IndustryConfig for downstream agents (persona, contexts, playbooks)
        industry_config = {}
        try:
            from hephae_api.workflows.orchestrators.industries import resolve
            cfg = resolve(business_type)
            industry_config = {
                "id": cfg.id,
                "name": cfg.name,
                "economistContext": cfg.economist_context,
                "scoutContext": cfg.scout_context,
                "synthesisContext": cfg.synthesis_context,
                "critiquePersona": cfg.critique_persona,
                "socialSearchTerms": list(cfg.social_search_terms),
            }
        except Exception as e:
            logger.warning(f"[BaseLayerFetcher] IndustryConfig resolve failed: {e}")

        # Write everything to session state via state_delta
        state_delta = {
            "rawSignals": signals,
            "signalsUsed": [k for k, v in signals.items() if v],
            "preComputedImpact": pre_computed,
            "matchedPlaybooks": matched_playbooks,
            "industryTrendSummary": industry_trend_summary,
            "industryConfig": industry_config,
            "techIntelligence": tech_intelligence,
        }

        logger.info(
            f"[BaseLayerFetcher] Done: {len(signals)} signals, "
            f"{len(pre_computed)} impact vars, {len(matched_playbooks)} playbooks"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta=state_delta),
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


# NOTE: Module-level agent instances REMOVED — ADK agents can only have one parent.
# All agent instantiation happens in create_pulse_orchestrator() factory function
# in pulse_orchestrator.py. Only export instruction builders and BaseLayerFetcher.
