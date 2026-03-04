"""
Marketing swarm agents + orchestrator function.

Pipeline: CreativeDirector -> PlatformRouter -> (Instagram/Blog) Copywriter.
Port of src/agents/marketing-swarm/*.ts.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from backend.config import AgentModels
from backend.lib.model_fallback import fallback_on_error
from backend.agents.marketing_swarm.prompts import (
    CREATIVE_DIRECTOR_INSTRUCTION,
    PLATFORM_ROUTER_INSTRUCTION,
    INSTAGRAM_COPYWRITER_INSTRUCTION,
    BLOG_COPYWRITER_INSTRUCTION,
)
from backend.lib.adk_helpers import user_msg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

creative_director_agent = LlmAgent(
    name="CreativeDirectorAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=CREATIVE_DIRECTOR_INSTRUCTION,
    output_key="creativeDirection",
    on_model_error_callback=fallback_on_error,
)

platform_router_agent = LlmAgent(
    name="PlatformRouterAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=PLATFORM_ROUTER_INSTRUCTION,
    output_key="platformDecision",
    on_model_error_callback=fallback_on_error,
)

instagram_copywriter_agent = LlmAgent(
    name="InstagramCopywriterAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=INSTAGRAM_COPYWRITER_INSTRUCTION,
    output_key="instagramDraft",
    on_model_error_callback=fallback_on_error,
)

blog_copywriter_agent = LlmAgent(
    name="BlogCopywriterAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=BLOG_COPYWRITER_INSTRUCTION,
    output_key="blogDraft",
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Core pipeline (returns results)
# ---------------------------------------------------------------------------

async def run_marketing_pipeline(identity: dict[str, Any]) -> dict[str, Any]:
    """Run the full marketing content pipeline and return structured results.

    Returns dict with keys: platform, creativeDirection, draft, summary.
    """
    business_name = identity.get("name", "Unknown")
    logger.info(f"[MarketingSwarm] Running pipeline for {business_name}...")

    session_service = InMemorySessionService()
    session_id = f"marketing-{int(time.time() * 1000)}"

    # Build context from identity
    context_parts = [f"Business: {business_name}"]
    if identity.get("address"):
        context_parts.append(f"Location: {identity['address']}")
    if identity.get("persona"):
        context_parts.append(f"Persona: {identity['persona']}")
    if identity.get("officialUrl"):
        context_parts.append(f"Website: {identity['officialUrl']}")
    social = identity.get("socialLinks") or {}
    if social:
        context_parts.append(f"Social: {json.dumps({k: v for k, v in social.items() if v})}")
    if identity.get("socialProfileMetrics"):
        summary_data = (identity["socialProfileMetrics"].get("summary") or {})
        if summary_data:
            context_parts.append(f"Social Presence Score: {summary_data.get('overallPresenceScore', 'N/A')}/100")
            context_parts.append(f"Strongest Platform: {summary_data.get('strongestPlatform', 'N/A')}")
    prompt = "\n".join(context_parts)

    # Step 1: Creative Director
    cd_runner = Runner(
        app_name="hephae-hub",
        agent=creative_director_agent,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys", state={}
    )

    async for _ in cd_runner.run_async(
        session_id=session_id, user_id="sys", new_message=user_msg(prompt),
    ):
        pass

    session = await session_service.get_session(
        app_name="hephae-hub", session_id=session_id, user_id="sys"
    )
    creative_direction = (session.state or {}).get("creativeDirection", "{}")

    # Step 2: Platform Router
    pr_session_id = f"platform-{int(time.time() * 1000)}"
    pr_runner = Runner(
        app_name="hephae-hub",
        agent=platform_router_agent,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="hephae-hub", session_id=pr_session_id, user_id="sys", state={}
    )

    async for _ in pr_runner.run_async(
        session_id=pr_session_id,
        user_id="sys",
        new_message=user_msg(f"Creative Direction:\n{creative_direction}"),
    ):
        pass

    pr_session = await session_service.get_session(
        app_name="hephae-hub", session_id=pr_session_id, user_id="sys"
    )
    platform_decision = (pr_session.state or {}).get("platformDecision", "{}")
    platform = "Instagram"
    try:
        pd = json.loads(platform_decision) if isinstance(platform_decision, str) else platform_decision
        platform = pd.get("platform", "Instagram")
    except Exception:
        pass

    # Step 3: Copywriter
    copywriter = instagram_copywriter_agent if platform == "Instagram" else blog_copywriter_agent
    cw_session_id = f"copy-{int(time.time() * 1000)}"
    cw_runner = Runner(
        app_name="hephae-hub",
        agent=copywriter,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="hephae-hub", session_id=cw_session_id, user_id="sys", state={}
    )

    async for _ in cw_runner.run_async(
        session_id=cw_session_id,
        user_id="sys",
        new_message=user_msg(
            f"Creative Direction:\n{creative_direction}\nPlatform: {platform}\nBusiness: {business_name}"
        ),
    ):
        pass

    cw_session = await session_service.get_session(
        app_name="hephae-hub", session_id=cw_session_id, user_id="sys"
    )
    output_key = "instagramDraft" if platform == "Instagram" else "blogDraft"
    draft = (cw_session.state or {}).get(output_key, "")

    result = {
        "platform": platform,
        "creativeDirection": creative_direction,
        "draft": draft,
        "summary": f"{platform} content strategy for {business_name}",
    }

    logger.info(f"[MarketingSwarm] Pipeline complete: platform={platform}, draft_len={len(str(draft))}")
    return result


# ---------------------------------------------------------------------------
# Fire-and-forget wrapper (used by other capabilities as background task)
# ---------------------------------------------------------------------------

async def generate_and_draft_marketing_content(
    report_data: Any,
    report_type: str,
) -> None:
    """Background orchestrator — runs pipeline and saves draft to Firestore."""
    business_name = "Unknown"
    try:
        identity = report_data.get("identity", {}) if isinstance(report_data, dict) else {}
        business_name = identity.get("name", "Unknown")

        result = await run_marketing_pipeline(identity)

        # Save to Firestore
        try:
            from backend.lib.firebase import db

            db.collection("marketing_drafts").add({
                "businessName": business_name,
                "reportType": report_type,
                "platform": result["platform"],
                "creativeDirection": result["creativeDirection"],
                "draft": result["draft"],
                "status": "pending_review",
                "createdAt": time.time(),
            })
            logger.info(f"[MarketingSwarm] Draft saved for {business_name} on {result['platform']}")
        except Exception as e:
            logger.error(f"[MarketingSwarm] Failed to save draft: {e}")

    except Exception as e:
        logger.error(f"[MarketingSwarm] Content generation failed for {business_name}: {e}")
