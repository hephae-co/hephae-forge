"""
IntelligenceFanOut — ADK ParallelAgent for research intelligence gathering.

Replaces the manual asyncio.gather of LLM research agents with an ADK-native
ParallelAgent. Each sub-agent writes to session.state via output_key, and
dynamic instructions read runtime context (area, industry, zips) from state.

API data sources (BLS, USDA, FDA, BigQuery) run alongside via asyncio.gather
since they're pure API calls, not LLM agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps.app import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.adk_helpers import user_msg
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool

from hephae_agents.research.industry_analyst import IndustryAnalystAgent
from hephae_agents.research.industry_news import IndustryNewsAgent
from hephae_agents.research.local_catalyst import LOCAL_CATALYST_INSTRUCTION
from hephae_agents.research.demographic_expert import DEMOGRAPHIC_EXPERT_INSTRUCTION

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic instruction builders — read runtime context from session.state
# ---------------------------------------------------------------------------

def _industry_analyst_instruction(ctx) -> str:
    """Inject sector from session state into IndustryAnalystAgent instruction."""
    sector = getattr(ctx, "state", {}).get("businessType", "unknown")
    base = IndustryAnalystAgent.instruction
    if callable(base):
        base = base(ctx)
    return f"{base}\n\nSECTOR: {sector}"


def _industry_news_instruction(ctx) -> str:
    """Inject industry + area from session state into IndustryNewsAgent instruction."""
    state = getattr(ctx, "state", {})
    industry = state.get("businessType", "unknown")
    area = state.get("area", "unknown")
    base = IndustryNewsAgent.instruction
    if callable(base):
        base = base(ctx)
    return f"{base}\n\nINDUSTRY: {industry}\nAREA: {area}"


def _local_catalyst_instruction(ctx) -> str:
    """Inject city/state/business from session state into LocalCatalystAgent instruction."""
    state = getattr(ctx, "state", {})
    city = state.get("city", "unknown")
    st = state.get("state", "")
    biz_type = state.get("businessType", "unknown")
    from datetime import datetime
    return (
        f"{LOCAL_CATALYST_INSTRUCTION}\n\n"
        f"TOWN/CITY: {city}\nSTATE: {st}\nBUSINESS TYPE: {biz_type}\n"
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"
    )


def _demographic_expert_instruction(ctx) -> str:
    """Inject area/state/zips from session state into DemographicExpertAgent instruction."""
    state = getattr(ctx, "state", {})
    area = state.get("area", "unknown")
    st = state.get("state", "")
    zips = state.get("completedZipCodes", [])
    zip_str = ", ".join(zips[:5]) if zips else ""
    return (
        f"{DEMOGRAPHIC_EXPERT_INSTRUCTION}\n\n"
        f"AREA: {area}\nSTATE: {st}\nZIP CODES: {zip_str}"
    )


# ---------------------------------------------------------------------------
# ParallelAgent sub-agents (each writes to session.state via output_key)
# ---------------------------------------------------------------------------

_industry_analyst_intel = LlmAgent(
    name="IndustryAnalystIntel",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    instruction=_industry_analyst_instruction,
    output_key="industryAnalysis",
    on_model_error_callback=fallback_on_error,
)

_industry_news_intel = LlmAgent(
    name="IndustryNewsIntel",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_industry_news_instruction,
    tools=[google_search],
    output_key="industryNews",
    on_model_error_callback=fallback_on_error,
)

_local_catalyst_intel = LlmAgent(
    name="LocalCatalystIntel",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_local_catalyst_instruction,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    output_key="localCatalysts",
    on_model_error_callback=fallback_on_error,
)

_demographic_expert_intel = LlmAgent(
    name="DemographicExpertIntel",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_demographic_expert_instruction,
    tools=[google_search],
    output_key="demographicData",
    on_model_error_callback=fallback_on_error,
)

# The fan-out: 4 LLM agents running in parallel
intelligence_fan_out = ParallelAgent(
    name="IntelligenceFanOut",
    sub_agents=[
        _industry_analyst_intel,
        _industry_news_intel,
        _local_catalyst_intel,
        _demographic_expert_intel,
    ],
)

# Context caching — reuses instruction prefixes across calls (saves ~30-40% prefill tokens)
_RESEARCH_CACHE_CONFIG = ContextCacheConfig(
    min_tokens=1024,    # Only cache if instruction exceeds 1K tokens
    ttl_seconds=900,    # 15 min cache (area research typically takes 5-10 min)
    cache_intervals=20, # Reuse across multiple zip codes in same research
)

_intel_app = App(
    name="hephae_research",
    root_agent=intelligence_fan_out,
    context_cache_config=_RESEARCH_CACHE_CONFIG,
)


# ---------------------------------------------------------------------------
# Runner — executes the ParallelAgent + API data sources
# ---------------------------------------------------------------------------

async def gather_intelligence(
    area: str,
    state: str,
    city: str,
    business_type: str,
    completed_zip_codes: list[str],
    dma_name: str = "",
    is_food: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run intelligence gathering using ADK ParallelAgent + API data sources.

    The 4 LLM research agents run via ADK's ParallelAgent (shared session.state).
    API data sources (BLS, USDA, FDA, BigQuery) run alongside via asyncio.gather.

    Returns: dict with keys matching IndustryIntelligence fields.
    """
    # Prepare session state with runtime context
    initial_state = {
        "area": area,
        "state": state,
        "city": city,
        "businessType": business_type,
        "completedZipCodes": completed_zip_codes,
    }

    if on_progress:
        on_progress("Running 4 LLM research agents in parallel...")

    # --- Run ADK ParallelAgent for LLM agents (with context caching) ---
    async def _run_llm_agents() -> dict[str, Any]:
        session_service = InMemorySessionService()
        session_id = f"intel-fanout-{id(initial_state)}"

        runner = Runner(app=_intel_app, session_service=session_service)
        await session_service.create_session(
            app_name="hephae_research",
            session_id=session_id,
            user_id="sys",
            state=initial_state,
        )
        async for _ in runner.run_async(
            session_id=session_id,
            user_id="sys",
            new_message=user_msg(
                f"Research the {business_type} sector in {area}, {state}. "
                f"Zip codes: {', '.join(completed_zip_codes[:5])}"
            ),
        ):
            pass

        session = await session_service.get_session(
            app_name="hephae_research", session_id=session_id, user_id="sys"
        )
        return dict(session.state or {})

    # --- Run API data sources in parallel ---
    async def _run_api_sources() -> dict[str, Any]:
        from hephae_db.bigquery.reader import query_industry_trends
        from hephae_integrations.bls_client import query_bls_cpi
        from hephae_integrations.fda_client import query_fda_enforcements
        from hephae_integrations.usda_client import query_usda_prices

        api_tasks: list[tuple[str, Any]] = []

        if dma_name:
            api_tasks.append(("industryTrends", query_industry_trends(dma_name, business_type)))
        if is_food:
            api_tasks.append(("fdaData", query_fda_enforcements(state)))
            api_tasks.append(("blsCpiData", query_bls_cpi(business_type)))
            api_tasks.append(("usdaPriceData", query_usda_prices(business_type, state)))

        if not api_tasks:
            return {}

        labels = [t[0] for t in api_tasks]
        coros = [t[1] for t in api_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        api_data: dict[str, Any] = {}
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                logger.error(f"[IntelFanOut] API source {label} failed: {result}")
            elif result is not None:
                api_data[label] = result
                logger.info(f"[IntelFanOut] API source {label} complete")

        return api_data

    # Run LLM agents and API sources in parallel
    llm_state, api_data = await asyncio.gather(_run_llm_agents(), _run_api_sources())

    # Extract LLM agent results from session state
    intel: dict[str, Any] = {}
    for key in ("industryAnalysis", "industryNews", "localCatalysts", "demographicData"):
        raw = llm_state.get(key)
        if raw:
            # output_key stores raw text — parse JSON if needed
            if isinstance(raw, str):
                try:
                    intel[key] = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    intel[key] = raw
            else:
                intel[key] = raw
            logger.info(f"[IntelFanOut] LLM agent {key} complete")

    # Merge API data
    intel.update(api_data)

    if on_progress:
        on_progress(f"Intelligence gathering complete ({len(intel)} sources)")

    return intel
