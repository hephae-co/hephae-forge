"""Social Media Auditor runner — stateless 2-stage pipeline via SequentialAgent.

Pipeline: SocialResearcher → SocialStrategist (session state handoff).
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

from hephae_capabilities.social.media_auditor.agent import social_audit_pipeline

logger = logging.getLogger(__name__)


async def run_social_media_audit(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run 2-stage social media audit via SequentialAgent pipeline.

    Args:
        identity: Enriched identity dict (must have name).
        business_context: Optional BusinessContext (unused currently).

    Returns:
        Social audit report dict with platforms, overall_score, etc.
    """
    business_name = identity.get("name")
    if not business_name:
        raise ValueError("Missing identity name for Social Media Audit")

    logger.info(f"[Social Audit Runner] Running for {business_name}...")

    session_service = kwargs.get("session_service") or InMemorySessionService()
    session_id = f"social-audit-{int(time.time() * 1000)}"
    user_id = "sys"

    # Load grounding memory from human-curated fixtures
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("social_media_auditor")

    # Pre-populate session state for dynamic instructions
    await session_service.create_session(
        app_name="social-audit",
        user_id=user_id,
        session_id=session_id,
        state={"identity": identity},
    )

    runner = Runner(
        app_name="social-audit",
        agent=social_audit_pipeline,
        session_service=session_service,
        memory_service=memory_service,
    )

    logger.info("[Social Audit Runner] Running SequentialAgent pipeline...")

    strategy_buffer = ""
    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg("Audit social media presence and generate strategy report."),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    continue
                if getattr(part, "text", None):
                    strategy_buffer += part.text

    # Parse JSON — with output_schema on the strategist, output should be valid JSON
    try:
        payload = json.loads(strategy_buffer)
    except json.JSONDecodeError:
        logger.warning("[Social Audit Runner] Native JSON parse failed, attempting fallback extraction")
        clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
        fb = clean_json_str.find("{")
        lb = clean_json_str.rfind("}")
        if fb != -1 and lb > fb:
            clean_json_str = clean_json_str[fb : lb + 1]
        payload = json.loads(clean_json_str)

    logger.info(
        f"[Social Audit Runner] Success: score={payload.get('overall_score')}, "
        f"platforms={len(payload.get('platforms', []))}"
    )
    return payload
