"""Grounding fixture loader — builds an InMemoryMemoryService from Firestore fixtures.

When an agent runner is given a memory_service, the agent can call load_memory_tool
to retrieve relevant past examples (few-shot grounding) before answering.

Flow:
  1. Admin marks a business output as "grounding" in the BusinessBrowser UI.
  2. The backend calls save_fixture_from_business(..., fixture_type="grounding").
  3. The backend calls register_fixture(fixture_id, "grounding", agent_key) async.
  4. At runner call time, the runner calls get_agent_memory_service(agent_key)
     which loads all grounding fixtures for that agent into a fresh
     InMemoryMemoryService and returns it.
  5. The runner passes memory_service=... to Runner(). The agent's load_memory_tool
     then retrieves relevant examples via keyword search.

Note: InMemoryMemoryService is not persistent — it is rebuilt per-request from
Firestore. This is acceptable because:
  - Grounding fixtures are rare (curated by admins, not per-user).
  - Firestore reads are fast (<100ms).
  - The memory service is only used during agent execution, not stored.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google.adk.events import Event
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import Session
from google.genai.types import Content, Part

from hephae_common.firebase import get_db
from hephae_db.eval.prompt_builders import build_eval_prompt

logger = logging.getLogger(__name__)

_COLLECTION = "test_fixtures"
_APP_NAME = "hephae-hub"
_GROUNDING_USER_ID = "grounding"


def _fixture_to_events(fixture: dict[str, Any], agent_key: str) -> list[Event]:
    """Convert a grounding fixture into a user+model event pair for memory injection."""
    identity = fixture.get("identity") or {}
    agent_output = fixture.get("agentOutput")

    if not identity.get("name"):
        return []

    # User turn: reconstruct the agent input prompt
    prompt = build_eval_prompt(agent_key, identity, fixture)
    user_event = Event(
        invocation_id=fixture.get("id", "grounding"),
        author="user",
        content=Content(role="user", parts=[Part(text=prompt)]),
    )

    events = [user_event]

    # Model turn: include the saved agent output as the example response
    if agent_output:
        if isinstance(agent_output, dict):
            output_text = json.dumps(agent_output, ensure_ascii=False)
        else:
            output_text = str(agent_output)

        model_event = Event(
            invocation_id=fixture.get("id", "grounding"),
            author="model",
            content=Content(role="model", parts=[Part(text=output_text)]),
        )
        events.append(model_event)

    return events


async def get_agent_memory_service(agent_key: str) -> InMemoryMemoryService | None:
    """Build a memory service pre-loaded with grounding fixtures for the given agent.

    Returns None if no grounding fixtures exist (caller should omit memory_service).
    """
    db = get_db()

    try:
        docs = await asyncio.to_thread(
            lambda: db.collection(_COLLECTION)
            .where("fixtureType", "==", "grounding")
            .where("agentKey", "==", agent_key)
            .order_by("savedAt", direction="DESCENDING")
            .limit(10)
            .get()
        )
    except Exception as e:
        error_msg = str(e)
        if "index" in error_msg.lower() or "requires an index" in error_msg.lower():
            logger.warning(
                f"[Grounding] Missing composite index for test_fixtures query "
                f"(fixtureType + agentKey + savedAt). Create it in Firestore console. "
                f"Agent {agent_key} will run without memory grounding."
            )
        else:
            logger.warning(
                f"[Grounding] Failed to load grounding fixtures for {agent_key}: {e}"
            )
        return None

    all_events: list[Event] = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        events = _fixture_to_events(data, agent_key)
        all_events.extend(events)

    if not all_events:
        logger.debug(f"[Grounding] No grounding fixtures found for agent_key={agent_key}")
        return None

    memory_service = InMemoryMemoryService()
    await memory_service.add_events_to_memory(
        app_name=_APP_NAME,
        user_id=_GROUNDING_USER_ID,
        events=all_events,
        session_id=f"grounding-{agent_key}",
    )

    logger.info(
        f"[Grounding] Loaded {len(all_events)} events ({len(all_events) // 2} fixtures) "
        f"into memory service for agent_key={agent_key}"
    )

    return memory_service


async def register_fixture(
    fixture_id: str,
    fixture_type: str,
    agent_key: str | None,
) -> None:
    """Called after saving a fixture to log registration.

    For grounding fixtures, no additional work is needed — the memory service is
    rebuilt from Firestore on each runner call. For test_case fixtures, they are
    picked up by FirestoreEvalSetsManager on the next eval run.

    This function exists as an extension point (e.g., future: warm a cache,
    trigger a re-evaluation, send a Slack notification, etc.).
    """
    logger.info(
        f"[Grounding] Registered fixture {fixture_id} "
        f"(type={fixture_type}, agent_key={agent_key})"
    )
