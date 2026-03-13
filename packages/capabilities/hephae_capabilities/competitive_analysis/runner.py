"""Competitive Analysis runner — stateless 2-stage pipeline via SequentialAgent.

Pipeline: CompetitorProfiler → MarketPositioning (session state handoff).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.adk_helpers import user_msg, _strip_markdown_fences

from hephae_capabilities.competitive_analysis.agent import competitive_pipeline

logger = logging.getLogger(__name__)


def _build_context_data(business_context: Any) -> str:
    """Build context enrichment string from BusinessContext admin data."""
    parts: list[str] = []
    if not business_context:
        return ""

    zr = getattr(business_context, "zipcode_research", None)
    if zr and isinstance(zr, dict):
        sections = zr.get("sections", {})
        if isinstance(sections, dict):
            if sections.get("demographics"):
                parts.append(
                    f"\n**LOCAL DEMOGRAPHICS (zip {getattr(business_context, 'zip_code', '')}):**\n"
                    f"{json.dumps(sections['demographics'], default=str)[:2000]}"
                )
            if sections.get("business_landscape"):
                parts.append(
                    f"\n**LOCAL BUSINESS LANDSCAPE:**\n"
                    f"{json.dumps(sections['business_landscape'], default=str)[:2000]}"
                )
            if sections.get("consumer_market"):
                parts.append(
                    f"\n**CONSUMER MARKET:**\n"
                    f"{json.dumps(sections['consumer_market'], default=str)[:1500]}"
                )

    ar = getattr(business_context, "area_research", None)
    if ar and isinstance(ar, dict):
        if ar.get("competitiveLandscape"):
            parts.append(
                f"\n**AREA COMPETITIVE LANDSCAPE:**\n"
                f"{json.dumps(ar['competitiveLandscape'], default=str)[:1500]}"
            )
        if ar.get("demographicFit"):
            parts.append(
                f"\n**DEMOGRAPHIC FIT:**\n"
                f"{json.dumps(ar['demographicFit'], default=str)[:1000]}"
            )

    return "\n".join(parts)


async def run_competitive_analysis(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run 2-stage competitive analysis via SequentialAgent pipeline.

    Args:
        identity: Enriched identity dict (must have competitors array).
        business_context: Optional BusinessContext with admin research data.

    Returns:
        Competitive report dict with market_summary, competitors, strategies, etc.
    """
    competitors = identity.get("competitors", [])
    if not competitors:
        raise ValueError("Missing competitors array. Please run discovery first.")

    session_service = kwargs.get("session_service") or InMemorySessionService()

    # Load grounding memory from human-curated fixtures
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("competitive_analyzer")

    # Pre-populate session state for dynamic instructions
    initial_state = {
        "identity": identity,
        "competitors": competitors,
        "contextData": _build_context_data(business_context),
    }

    session_id = f"comp-{int(time.time() * 1000)}"
    user_id = "sys"

    await session_service.create_session(
        app_name="competitive-analysis",
        user_id=user_id,
        session_id=session_id,
        state=initial_state,
    )

    logger.info("[Competitive Runner] Running SequentialAgent pipeline...")

    runner = Runner(
        app_name="competitive-analysis",
        agent=competitive_pipeline,
        session_service=session_service,
        memory_service=memory_service,
    )

    # Collect final output text from the positioning agent
    strategy_buffer = ""
    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg("Analyze competitors and generate competitive positioning report."),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    continue
                if getattr(part, "text", None):
                    strategy_buffer += part.text

    # Native structured output — market_positioning_agent has output_schema=CompetitiveAnalysisOutput
    try:
        payload = json.loads(strategy_buffer)
    except json.JSONDecodeError:
        logger.warning("[Competitive Runner] Native JSON parse failed, attempting fallback extraction")
        clean = _strip_markdown_fences(strategy_buffer)
        fb = clean.find("{")
        lb = clean.rfind("}")
        if fb != -1 and lb > fb:
            clean = clean[fb : lb + 1]
        payload = json.loads(clean)

    logger.info(f"[Competitive Runner] Success: {list(payload.keys())}")
    return payload
