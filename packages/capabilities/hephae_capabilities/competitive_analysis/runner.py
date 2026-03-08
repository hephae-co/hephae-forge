"""Competitive Analysis runner — stateless 2-stage pipeline.

Stage 1: Competitor Profiler — researches competitors
Stage 2: Market Positioning — synthesizes competitive strategy JSON
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.adk_helpers import user_msg

from hephae_capabilities.competitive_analysis.agent import (
    competitor_profiler_agent,
    market_positioning_agent,
)

logger = logging.getLogger(__name__)


async def run_competitive_analysis(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run 2-stage competitive analysis pipeline.

    Args:
        identity: Enriched identity dict (must have competitors array).
        business_context: Optional BusinessContext with admin research data.

    Returns:
        Competitive report dict with market_summary, competitors, strategies, etc.
    """
    competitors = identity.get("competitors", [])
    if not competitors:
        raise ValueError("Missing competitors array. Please run discovery first.")

    session_service = InMemorySessionService()

    # Load grounding memory from human-curated fixtures (few-shot examples)
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("competitive_analyzer")

    runner = Runner(
        app_name="competitive-analysis",
        agent=competitor_profiler_agent,
        session_service=session_service,
        memory_service=memory_service,
    )
    session_id = f"comp-{int(time.time() * 1000)}"
    user_id = "sys"

    await session_service.create_session(
        app_name="competitive-analysis", user_id=user_id, session_id=session_id, state={}
    )

    # Step 1: Profile Competitors
    logger.info("[Competitive Runner] Step 1: Profiling Competitors...")

    profiler_parts = [f"Research these competitors: {json.dumps(competitors)}"]
    if business_context:
        zr = getattr(business_context, "zipcode_research", None)
        if zr and isinstance(zr, dict):
            sections = zr.get("sections", {})
            if isinstance(sections, dict):
                if sections.get("demographics"):
                    profiler_parts.append(
                        f"\n**LOCAL DEMOGRAPHICS (zip {getattr(business_context, 'zip_code', '')}):**\n"
                        f"{json.dumps(sections['demographics'], default=str)[:2000]}"
                    )
                if sections.get("business_landscape"):
                    profiler_parts.append(
                        f"\n**LOCAL BUSINESS LANDSCAPE:**\n"
                        f"{json.dumps(sections['business_landscape'], default=str)[:2000]}"
                    )
                if sections.get("consumer_market"):
                    profiler_parts.append(
                        f"\n**CONSUMER MARKET:**\n"
                        f"{json.dumps(sections['consumer_market'], default=str)[:1500]}"
                    )
        ar = getattr(business_context, "area_research", None)
        if ar and isinstance(ar, dict):
            if ar.get("competitiveLandscape"):
                profiler_parts.append(
                    f"\n**AREA COMPETITIVE LANDSCAPE:**\n"
                    f"{json.dumps(ar['competitiveLandscape'], default=str)[:1500]}"
                )
            if ar.get("demographicFit"):
                profiler_parts.append(
                    f"\n**DEMOGRAPHIC FIT:**\n"
                    f"{json.dumps(ar['demographicFit'], default=str)[:1000]}"
                )

    profiler_prompt = "\n".join(profiler_parts)

    competitor_brief = ""
    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(profiler_prompt),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    continue
                if getattr(part, "text", None):
                    competitor_brief += part.text

    # Step 2: Market Positioning
    logger.info("[Competitive Runner] Step 2: Running Market Strategy...")
    positioning_runner = Runner(
        app_name="competitive-analysis",
        agent=market_positioning_agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    strategy_prompt = (
        f"TARGET RESTAURANT: {json.dumps(identity)}\n\n"
        f"COMPETITORS BRIEF:\n{competitor_brief}\n\n"
        "Generate the final competitive json report."
    )

    strategy_buffer = ""
    async for raw_event in positioning_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(strategy_prompt),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    continue
                if getattr(part, "text", None):
                    strategy_buffer += part.text

    # Robust JSON extraction
    clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
    clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
    fb = clean_json_str.find("{")
    lb = clean_json_str.rfind("}")
    if fb != -1 and lb > fb:
        clean_json_str = clean_json_str[fb : lb + 1]
    payload = json.loads(clean_json_str)

    logger.info(f"[Competitive Runner] Success: {list(payload.keys())}")
    return payload
