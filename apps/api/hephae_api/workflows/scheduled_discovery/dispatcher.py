"""CapabilityDispatcherAgent — decides which capability runners to invoke per business.

After a business passes the quality gate, this agent receives the full profile
and decides which capabilities are worth running based on data availability.

This avoids wasting compute on:
  - SEO audit when there is no website URL
  - Margin surgery when there is no menu data
  - Competitive analysis when competitors haven't been discovered yet
  - Social audit when no social links or brand presence exists

Uses ADK FunctionTools wrapping the existing runner functions. The agent
calls them directly — each tool call IS the capability run. Results are
persisted to Firestore inside each tool.

Model: PRIMARY_MODEL (cheapest) — the decisions here are simple enough
that we don't need a reasoning-heavy model.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg
from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

_DISPATCHER_INSTRUCTION = """You are a capability dispatcher for Hephae, deciding which analysis
tools to run for an independent local business that has just been discovered.

You have these tools available:
  - run_seo_audit: Full SEO analysis. ONLY call if the business has a website URL.
  - run_traffic_forecast: Foot traffic forecast. ONLY call if business has address + coordinates.
  - run_competitive_analysis: Competitive landscape. ONLY call if business has known competitors.
  - run_margin_analysis: Menu margin surgery. ONLY call if business has menu data or is in food/drink category.
  - run_social_media_audit: Social media presence. ONLY call if business has social links OR is consumer-facing with a web presence.

Call tools sequentially — do NOT call multiple tools at once.
After calling all appropriate tools, call finish() to signal completion.

Be conservative: if data is missing or marginal, skip that capability.
Running a capability on insufficient data wastes resources and produces low-quality output.
"""


def _make_capability_tools(
    biz_id: str,
    identity: dict[str, Any],
    results: dict[str, Any],
) -> list[FunctionTool]:
    """Build FunctionTools that run capability runners and persist results."""

    async def _persist(capability_key: str, result: dict) -> None:
        if not result:
            return
        db = get_db()
        from datetime import datetime
        result["runAt"] = datetime.utcnow().isoformat()
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update,
            {f"latestOutputs.{capability_key}": result},
        )

    async def run_seo_audit() -> str:
        """Run SEO audit for this business. Requires a website URL."""
        try:
            from hephae_agents.seo_auditor.runner import run_seo_audit as _run
            result = await _run(identity)
            if result:
                await _persist("seo_auditor", result)
                results["seo_auditor"] = "completed"
                score = result.get("overallScore", result.get("score", "?"))
                return f"SEO audit complete. Score: {score}/100."
            return "SEO audit returned no data."
        except Exception as e:
            logger.error(f"[Dispatcher] SEO audit failed for {biz_id}: {e}")
            results["seo_auditor"] = f"failed: {e}"
            return f"SEO audit failed: {e}"

    async def run_traffic_forecast() -> str:
        """Run foot traffic forecast for this business. Requires address and coordinates."""
        try:
            from hephae_agents.traffic_forecaster.runner import run_traffic_forecast as _run
            result = await _run(identity)
            if result:
                await _persist("traffic_forecaster", result)
                results["traffic_forecaster"] = "completed"
                return "Traffic forecast complete."
            return "Traffic forecast returned no data."
        except Exception as e:
            logger.error(f"[Dispatcher] Traffic forecast failed for {biz_id}: {e}")
            results["traffic_forecaster"] = f"failed: {e}"
            return f"Traffic forecast failed: {e}"

    async def run_competitive_analysis() -> str:
        """Run competitive analysis. Requires known competitors in the profile."""
        try:
            from hephae_agents.competitive_analysis.runner import run_competitive_analysis as _run
            result = await _run(identity)
            if result:
                await _persist("competitive_analyzer", result)
                results["competitive_analyzer"] = "completed"
                count = len(result.get("competitors", []))
                return f"Competitive analysis complete. Profiled {count} competitors."
            return "Competitive analysis returned no data."
        except Exception as e:
            logger.error(f"[Dispatcher] Competitive analysis failed for {biz_id}: {e}")
            results["competitive_analyzer"] = f"failed: {e}"
            return f"Competitive analysis failed: {e}"

    async def run_margin_analysis() -> str:
        """Run menu margin surgery. Best for food/drink businesses with menu data."""
        try:
            from hephae_agents.margin_analyzer.runner import run_margin_analysis as _run
            result = await _run(identity)
            if result:
                await _persist("margin_surgeon", result)
                results["margin_surgeon"] = "completed"
                score = result.get("overall_score", result.get("score", "?"))
                return f"Margin analysis complete. Score: {score}/100."
            return "Margin analysis returned no data."
        except Exception as e:
            logger.error(f"[Dispatcher] Margin analysis failed for {biz_id}: {e}")
            results["margin_surgeon"] = f"failed: {e}"
            return f"Margin analysis failed: {e}"

    async def run_social_media_audit() -> str:
        """Run social media audit. Useful for consumer-facing businesses."""
        try:
            from hephae_agents.social.media_auditor.runner import run_social_media_audit as _run
            result = await _run(identity)
            if result:
                await _persist("social_media_auditor", result)
                results["social_media_auditor"] = "completed"
                score = result.get("overall_score", result.get("score", "?"))
                return f"Social media audit complete. Score: {score}/100."
            return "Social media audit returned no data."
        except Exception as e:
            logger.error(f"[Dispatcher] Social media audit failed for {biz_id}: {e}")
            results["social_media_auditor"] = f"failed: {e}"
            return f"Social media audit failed: {e}"

    def finish() -> str:
        """Signal that all appropriate capabilities have been dispatched."""
        return "Dispatch complete."

    return [
        FunctionTool(func=run_seo_audit),
        FunctionTool(func=run_traffic_forecast),
        FunctionTool(func=run_competitive_analysis),
        FunctionTool(func=run_margin_analysis),
        FunctionTool(func=run_social_media_audit),
        FunctionTool(func=finish),
    ]


def _build_profile_prompt(identity: dict[str, Any]) -> str:
    """Build the prompt for the dispatcher agent."""
    has_url = bool(identity.get("officialUrl"))
    has_coords = bool(identity.get("coordinates"))
    has_competitors = bool(identity.get("competitors"))
    has_menu = bool(identity.get("menuData") or identity.get("menuUrl"))
    has_social = bool({k: v for k, v in (identity.get("socialLinks") or {}).items() if v})
    category = identity.get("category", "")
    is_food = any(
        kw in category.lower()
        for kw in ("restaurant", "cafe", "bar", "pizza", "food", "drink", "bakery", "deli")
    ) if category else False

    lines = [
        f"Business: {identity.get('name', 'Unknown')}",
        f"Category: {category or 'unknown'}",
        f"Address: {identity.get('address', '')}",
        f"Has website URL: {has_url}",
        f"Has GPS coordinates: {has_coords}",
        f"Has known competitors: {has_competitors} ({len(identity.get('competitors', []))} found)",
        f"Has menu data: {has_menu}",
        f"Has social links: {has_social}",
        f"Is food/drink category: {is_food}",
    ]

    lines.append("\nDecide which capability tools to run based on data availability.")
    return "\n".join(lines)


async def run_capability_dispatcher(
    biz_id: str,
    identity: dict[str, Any],
) -> dict[str, str]:
    """Run the dispatcher agent to selectively invoke capability runners.

    Returns a dict mapping capability_key → "completed" | "failed: ..." | "skipped".
    """
    results: dict[str, str] = {}
    tools = _make_capability_tools(biz_id, identity, results)

    agent = LlmAgent(
        name="CapabilityDispatcher",
        model=AgentModels.PRIMARY_MODEL,
        instruction=_DISPATCHER_INSTRUCTION,
        tools=tools,
        on_model_error_callback=fallback_on_error,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="hephae-hub",
        agent=agent,
        session_service=session_service,
    )

    session_id = f"dispatch-{int(time.time() * 1000)}"
    await session_service.create_session(
        app_name="hephae-hub", user_id="batch", session_id=session_id, state={}
    )

    prompt = _build_profile_prompt(identity)

    try:
        async for _ in runner.run_async(
            user_id="batch",
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            pass
    except Exception as e:
        logger.error(f"[Dispatcher] Agent error for {biz_id}: {e}")

    completed = [k for k, v in results.items() if v == "completed"]
    failed = [k for k, v in results.items() if v.startswith("failed")]
    logger.info(
        f"[Dispatcher] {biz_id}: completed={completed}, failed={failed}"
    )

    return results
