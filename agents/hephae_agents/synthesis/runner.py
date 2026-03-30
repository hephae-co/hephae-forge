"""Synthesis runner — executes industry and zip digest ADK pipelines.

Usage:
    from hephae_agents.synthesis.runner import generate_industry_digest, generate_zip_digest

    digest = await generate_industry_digest("restaurant", "2026-W13")
    digest = await generate_zip_digest("07110", "Restaurants", "2026-W13")
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)


async def generate_industry_digest(
    industry_key: str,
    week_of: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Run the industry digest ADK pipeline and persist to Firestore.

    Returns the generated digest dict.
    """
    from hephae_agents.synthesis.industry_digest import create_industry_digest_agent
    from hephae_db.firestore.industry_digests import save_industry_digest

    logger.info(f"[Synthesis] Generating industry digest: {industry_key} ({week_of})")
    start = time.time()

    agent = create_industry_digest_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="synthesis",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="synthesis",
        user_id="system",
        state={
            "industryKey": industry_key,
            "weekOf": week_of,
            "displayName": display_name or industry_key.replace("_", " ").title(),
        },
    )

    # Run pipeline
    async for _ in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_msg(f"Synthesize industry digest for {industry_key}, week {week_of}."),
    ):
        pass

    # Extract result
    session = await session_service.get_session(
        app_name="synthesis",
        user_id="system",
        session_id=session.id,
    )
    final_state = dict(session.state or {})
    digest = final_state.get("industryDigest", {})

    if not digest:
        logger.warning(f"[Synthesis] Empty industry digest for {industry_key}")
        return {}

    # Persist
    doc_id = await save_industry_digest(industry_key, week_of, digest)
    digest["id"] = doc_id

    elapsed = time.time() - start
    logger.info(f"[Synthesis] Industry digest {industry_key} done in {elapsed:.1f}s")
    return digest


async def generate_zip_digest(
    zip_code: str,
    business_type: str,
    week_of: str,
    city: str = "",
    state: str = "",
    county: str = "",
    industry_key: str = "",
) -> dict[str, Any]:
    """Run the zip digest ADK pipeline and persist to Firestore.

    Returns the generated digest dict.
    """
    from hephae_agents.synthesis.zip_digest import create_zip_digest_agent
    from hephae_db.firestore.weekly_digests import save_weekly_digest

    logger.info(f"[Synthesis] Generating zip digest: {zip_code} ({business_type}, {week_of})")
    start = time.time()

    agent = create_zip_digest_agent()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="synthesis",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="synthesis",
        user_id="system",
        state={
            "zipCode": zip_code,
            "businessType": business_type,
            "weekOf": week_of,
            "city": city,
            "state": state,
            "county": county,
            "industryKey": industry_key,
        },
    )

    # Run pipeline
    async for _ in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_msg(
            f"Synthesize weekly digest for {business_type} in {zip_code} ({city}, {state}), week {week_of}."
        ),
    ):
        pass

    # Extract result
    session = await session_service.get_session(
        app_name="synthesis",
        user_id="system",
        session_id=session.id,
    )
    final_state = dict(session.state or {})
    digest = final_state.get("zipDigest", {})

    if not digest:
        logger.warning(f"[Synthesis] Empty zip digest for {zip_code}")
        return {}

    # Persist
    doc_id = await save_weekly_digest(zip_code, business_type, week_of, digest)
    digest["id"] = doc_id

    elapsed = time.time() - start
    logger.info(f"[Synthesis] Zip digest {zip_code}/{business_type} done in {elapsed:.1f}s")
    return digest


async def generate_research_digest(
    vertical: str,
    week_of: str,
) -> dict[str, Any]:
    """Run the research digest ADK pipeline and persist to Firestore."""
    from hephae_agents.synthesis.research_digest import create_research_digest_agent
    from hephae_db.firestore.research_digests import save_research_digest

    logger.info(f"[Synthesis] Generating research digest: {vertical} ({week_of})")
    start = time.time()

    agent = create_research_digest_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="synthesis", session_service=session_service)

    session = await session_service.create_session(
        app_name="synthesis", user_id="system",
        state={"vertical": vertical, "weekOf": week_of},
    )

    async for _ in runner.run_async(
        user_id="system", session_id=session.id,
        new_message=user_msg(f"Synthesize research digest for {vertical}, week {week_of}."),
    ):
        pass

    session = await session_service.get_session(app_name="synthesis", user_id="system", session_id=session.id)
    digest = dict(session.state or {}).get("researchDigest", {})

    if not digest:
        logger.warning(f"[Synthesis] Empty research digest for {vertical}")
        return {}

    doc_id = await save_research_digest(vertical, week_of, digest)
    digest["id"] = doc_id

    elapsed = time.time() - start
    logger.info(f"[Synthesis] Research digest {vertical} done in {elapsed:.1f}s")
    return digest


async def generate_ai_tools_digest(
    vertical: str,
    week_of: str,
) -> dict[str, Any]:
    """Run the AI tools digest ADK pipeline and persist to Firestore."""
    from hephae_agents.synthesis.ai_tools_digest import create_ai_tools_digest_agent
    from hephae_db.firestore.ai_tools_digests import save_ai_tools_digest

    logger.info(f"[Synthesis] Generating AI tools digest: {vertical} ({week_of})")
    start = time.time()

    agent = create_ai_tools_digest_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="synthesis", session_service=session_service)

    session = await session_service.create_session(
        app_name="synthesis", user_id="system",
        state={"vertical": vertical, "weekOf": week_of},
    )

    async for _ in runner.run_async(
        user_id="system", session_id=session.id,
        new_message=user_msg(f"Synthesize AI tools digest for {vertical}, week {week_of}."),
    ):
        pass

    session = await session_service.get_session(app_name="synthesis", user_id="system", session_id=session.id)
    digest = dict(session.state or {}).get("aiToolsDigest", {})

    if not digest:
        logger.warning(f"[Synthesis] Empty AI tools digest for {vertical}")
        return {}

    doc_id = await save_ai_tools_digest(vertical, week_of, digest)
    digest["id"] = doc_id

    elapsed = time.time() - start
    logger.info(f"[Synthesis] AI tools digest {vertical} done in {elapsed:.1f}s")
    return digest
