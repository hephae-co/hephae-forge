"""Shared ADK agent execution helpers — eliminates repetitive boilerplate across all agents."""

import json
import logging
import re
import uuid

from google.adk import Runner
from google.adk.agents import LlmAgent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps.app import App
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# Reusable session service — one per process
_session_service = InMemorySessionService()

# Cache App instances so ADK can reuse server-side context caches across calls
_app_cache: dict[str, App] = {}

_DEFAULT_CACHE_CONFIG = ContextCacheConfig(
    min_tokens=1024,     # Flash minimum; Pro's 4096 enforced by API
    ttl_seconds=900,     # 15 minutes — covers a full workflow phase
    cache_intervals=50,  # Reuse up to 50 times before refresh
)


def _get_or_create_app(agent: LlmAgent, app_name: str) -> App:
    """Get or create a cached App instance for an agent."""
    key = f"{app_name}:{agent.name}"
    if key not in _app_cache:
        _app_cache[key] = App(
            name=app_name,
            root_agent=agent,
            context_cache_config=_DEFAULT_CACHE_CONFIG,
        )
    return _app_cache[key]


def user_msg(text: str) -> genai_types.Content:
    """Create a user message Content object."""
    return genai_types.Content(role="user", parts=[genai_types.Part(text=text)])


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def run_agent_to_text(
    agent: LlmAgent,
    prompt: str,
    app_name: str = "HephaeAdmin",
    state: dict | None = None,
) -> str:
    """Run an agent and return the last text output."""
    session_id = f"{agent.name}-{uuid.uuid4().hex[:8]}"
    user_id = "system"

    app = _get_or_create_app(agent, app_name)

    session = await _session_service.create_session(
        app_name=app_name, session_id=session_id, user_id=user_id, state=state or {}
    )

    runner = Runner(app=app, session_service=_session_service)

    last_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_msg(prompt),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    last_text = part.text

    return last_text


async def run_agent_to_json(
    agent: LlmAgent,
    prompt: str,
    app_name: str = "HephaeAdmin",
    state: dict | None = None,
) -> dict | list | None:
    """Run an agent, extract text, strip markdown fences, and parse as JSON."""
    raw = await run_agent_to_text(agent, prompt, app_name, state)
    if not raw:
        logger.warning(f"[ADK] Agent {agent.name} returned empty output")
        return None

    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[ADK] Failed to parse JSON from {agent.name}: {e}")
        logger.debug(f"[ADK] Raw output: {raw[:500]}")
        return None
