"""Social Media Auditor runner — stateless 2-stage pipeline.

Stage 1: Social Researcher — investigates social presence
Stage 2: Social Strategist — synthesizes audit JSON report
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

from hephae_capabilities.social.media_auditor.agent import (
    social_researcher_agent,
    social_strategist_agent,
)

logger = logging.getLogger(__name__)


async def run_social_media_audit(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run 2-stage social media audit pipeline.

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

    session_service = InMemorySessionService()
    session_id = f"social-audit-{int(time.time() * 1000)}"
    user_id = "sys"

    await session_service.create_session(
        app_name="social-audit", user_id=user_id, session_id=session_id, state={}
    )

    # Load grounding memory from human-curated fixtures (few-shot examples)
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("social_media_auditor")

    # Step 1: Social Researcher
    logger.info("[Social Audit Runner] Step 1: Researching social presence...")

    researcher_parts = [f"Business: {business_name}"]
    if identity.get("address"):
        researcher_parts.append(f"Location: {identity['address']}")
    if identity.get("persona"):
        researcher_parts.append(f"Persona: {identity['persona']}")
    if identity.get("officialUrl"):
        researcher_parts.append(f"Website: {identity['officialUrl']}")

    social = identity.get("socialLinks") or {}
    active_social = {k: v for k, v in social.items() if v}
    if active_social:
        researcher_parts.append(f"\nKNOWN SOCIAL LINKS:\n{json.dumps(active_social, indent=2)}")

    spm = identity.get("socialProfileMetrics")
    if spm:
        researcher_parts.append(
            f"\nEXISTING DISCOVERY METRICS:\n{json.dumps(spm, default=str)[:3000]}"
        )

    competitors = identity.get("competitors", [])
    if competitors:
        researcher_parts.append(
            f"\nCOMPETITORS:\n{json.dumps(competitors[:5], default=str)}"
        )

    researcher_prompt = "\n".join(researcher_parts)

    runner = Runner(
        app_name="social-audit",
        agent=social_researcher_agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    research_brief = ""
    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(researcher_prompt),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    continue
                if getattr(part, "text", None):
                    research_brief += part.text

    # Step 2: Social Strategist
    logger.info("[Social Audit Runner] Step 2: Synthesizing strategy...")

    strategist_runner = Runner(
        app_name="social-audit",
        agent=social_strategist_agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    strategy_prompt = (
        f"TARGET BUSINESS: {json.dumps(identity, default=str)[:4000]}\n\n"
        f"SOCIAL MEDIA RESEARCH BRIEF:\n{research_brief}\n\n"
        "Generate the final social media audit JSON report."
    )

    strategy_buffer = ""
    async for raw_event in strategist_runner.run_async(
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

    # Parse JSON
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
