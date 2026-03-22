"""Tech Intelligence runner — generates technology landscape profiles per vertical.

Runs the TechScout ADK pipeline and saves results to Firestore.
Called by the tech intelligence cron (Sunday 1 AM ET).
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


async def generate_tech_intelligence(vertical: str) -> dict[str, Any]:
    """Generate technology intelligence for a vertical.

    Returns the TechProfile dict (platforms, aiOpportunities, etc.)
    """
    from hephae_agents.research.tech_scout import create_tech_scout
    from hephae_db.firestore.tech_intelligence import save_tech_intelligence

    week_of = _current_iso_week()
    logger.info(f"[TechIntel] Starting tech intelligence for {vertical} ({week_of})")

    pipeline = create_tech_scout(vertical)

    session_service = InMemorySessionService()
    session_id = f"tech-{vertical}-{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(
        app_name="tech_intelligence",
        session_id=session_id,
        user_id="system",
        state={"vertical": vertical, "weekOf": week_of},
    )

    runner = Runner(
        agent=pipeline,
        app_name="tech_intelligence",
        session_service=session_service,
    )

    prompt = (
        f"Research the current technology landscape for {vertical} businesses. "
        f"Find the latest tools, AI capabilities, platform updates, and community recommendations. "
        f"Focus on what's new in the last 30 days."
    )

    last_text = ""
    try:
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=user_msg(prompt),
            run_config=RunConfig(max_llm_calls=15),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text
    except Exception as e:
        logger.error(f"[TechIntel] Pipeline failed for {vertical}: {e}")
        return {"error": str(e)}

    # Parse JSON from output
    profile: dict[str, Any] = {}
    if last_text:
        try:
            profile = json.loads(last_text)
        except json.JSONDecodeError:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', last_text)
            if match:
                try:
                    profile = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

    if not profile or not isinstance(profile, dict):
        # Try reading from session state
        final_session = await session_service.get_session(
            app_name="tech_intelligence",
            session_id=session.id,
            user_id="system",
        )
        if final_session and final_session.state:
            tp = final_session.state.get("techProfile", "")
            if tp and isinstance(tp, str):
                try:
                    profile = json.loads(tp)
                except json.JSONDecodeError:
                    pass
            elif isinstance(tp, dict):
                profile = tp

    if not profile:
        logger.warning(f"[TechIntel] No structured output for {vertical}")
        return {"error": "no_output", "rawText": last_text[:500] if last_text else ""}

    # Save to Firestore
    doc_id = await save_tech_intelligence(vertical, week_of, profile)

    logger.info(
        f"[TechIntel] Complete for {vertical}: "
        f"{len(profile.get('aiOpportunities', []))} AI opportunities, "
        f"{len(profile.get('platforms', {}))} platform categories"
    )

    return {
        "vertical": vertical,
        "weekOf": week_of,
        "docId": doc_id,
        **profile,
    }
