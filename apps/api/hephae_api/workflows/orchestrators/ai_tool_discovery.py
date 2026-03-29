"""AI Tool Discovery runner — generates AI tool profiles per vertical.

Runs the AiToolScout ADK pipeline and saves results to BigQuery.
Called by the AI tool discovery cron (Tuesday 7 AM ET) or manually from admin.

Storage: hephae.ai_tools + hephae.ai_tool_runs (BQ only, no Firestore).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from google.adk.runners import RunConfig, Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)


def _current_iso_week() -> str:
    now = datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


async def generate_ai_tool_discovery(
    vertical: str,
    force: bool = False,
    test_mode: bool = False,
) -> dict[str, Any]:
    """Generate AI tool discovery for a vertical.

    Args:
        vertical: Normalized vertical key (e.g., "restaurant").
        force: If True, regenerate even if a run already exists for this week.
        test_mode: If True, mark with testMode=True and 24h expireAt TTL.

    Returns dict with tools[], weeklyHighlight, docId, weekOf, stats.
    """
    from hephae_agents.research.ai_tool_scout import create_ai_tool_scout
    from hephae_db.bigquery.ai_tools import (
        get_ai_tool_run,
        save_ai_tool_run,
    )

    week_of = _current_iso_week()

    # Idempotency check — skip if already exists for this week
    if not force and not test_mode:
        existing = await get_ai_tool_run(vertical, week_of)
        if existing:
            logger.info(
                f"[AiToolDiscovery] Run already exists for {vertical}/{week_of} — skipping"
            )
            return {**existing, "skipped": True}

    logger.info(f"[AiToolDiscovery] Starting discovery for {vertical} ({week_of})")

    pipeline = create_ai_tool_scout(vertical)

    session_service = InMemorySessionService()
    session_id = f"aitool-{vertical}-{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(
        app_name="ai_tool_discovery",
        session_id=session_id,
        user_id="system",
        state={"vertical": vertical, "weekOf": week_of},
    )

    runner = Runner(
        agent=pipeline,
        app_name="ai_tool_discovery",
        session_service=session_service,
    )

    prompt = (
        f"Discover the best AI-powered tools available right now for {vertical} small business owners. "
        f"Prioritize free tools that owners can use immediately without any technical setup. "
        f"Find practical, actionable AI capabilities across all key operational categories. "
        f"Focus on established, reputable tools with real users — and call out any free tools "
        f"that replace expensive software the owner might already be paying for."
    )

    last_text = ""
    try:
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=user_msg(prompt),
            run_config=RunConfig(max_llm_calls=20),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text
    except Exception as e:
        logger.error(f"[AiToolDiscovery] Pipeline failed for {vertical}: {e}")
        return {"error": str(e)}

    # Parse JSON from synthesizer output
    profile: dict[str, Any] = {}
    if last_text:
        try:
            profile = json.loads(last_text)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", last_text)
            if match:
                try:
                    profile = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

    if not profile or not isinstance(profile, dict):
        # Fallback: read from session state
        final_session = await session_service.get_session(
            app_name="ai_tool_discovery",
            session_id=session.id,
            user_id="system",
        )
        if final_session and final_session.state:
            tp = final_session.state.get("aiToolProfile", "")
            if isinstance(tp, str) and tp:
                try:
                    profile = json.loads(tp)
                except json.JSONDecodeError:
                    pass
            elif isinstance(tp, dict):
                profile = tp

    if not profile:
        logger.warning(f"[AiToolDiscovery] No structured output for {vertical}")
        return {"error": "no_output", "rawText": last_text[:500] if last_text else ""}

    tools: list[dict[str, Any]] = profile.get("tools", [])
    weekly_highlight: dict[str, str] = profile.get("weeklyHighlight", {})

    doc_id = await save_ai_tool_run(
        vertical=vertical,
        week_of=week_of,
        tools=tools,
        weekly_highlight=weekly_highlight,
        test_mode=test_mode,
    )

    new_count = len([t for t in tools if t.get("isNew")])
    high_count = len([t for t in tools if t.get("relevanceScore") == "HIGH"])
    free_count = len([t for t in tools if t.get("isFree")])

    logger.info(
        f"[AiToolDiscovery] Complete for {vertical}: "
        f"{len(tools)} tools, {new_count} new, {free_count} free, {high_count} high relevance"
    )

    return {
        "vertical": vertical,
        "weekOf": week_of,
        "docId": doc_id,
        "tools": tools,
        "weeklyHighlight": weekly_highlight,
        "totalToolsFound": len(tools),
        "newToolsCount": new_count,
        "highRelevanceCount": high_count,
        "freeToolsCount": free_count,
    }
