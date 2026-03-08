"""Shared ADK agent execution helpers — deduplicated from web + admin.

Provides both simple helpers (user_msg, user_msg_with_image) and
full runner functions (run_agent_to_text, run_agent_to_json).

Supports native structured outputs via ADK's response_schema parameter,
eliminating manual JSON parsing and markdown stripping.
"""

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
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_session_service = InMemorySessionService()
_app_cache: dict[str, App] = {}

_DEFAULT_CACHE_CONFIG = ContextCacheConfig(
    min_tokens=1024,
    ttl_seconds=900,
    cache_intervals=50,
)


def _get_or_create_app(agent: LlmAgent, app_name: str) -> App:
    key = f"{app_name}:{agent.name}"
    if key not in _app_cache:
        _app_cache[key] = App(
            name=app_name,
            root_agent=agent,
            context_cache_config=_DEFAULT_CACHE_CONFIG,
        )
    return _app_cache[key]


def user_msg(text: str) -> genai_types.Content:
    """Build a simple text Content for runner.run_async(new_message=...)."""
    return genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=text)])


def user_msg_with_image(text: str, image_b64: str, mime_type: str = "image/jpeg") -> genai_types.Content:
    """Build a Content with text + inline image data."""
    return genai_types.Content(
        role="user",
        parts=[
            genai_types.Part.from_text(text=text),
            genai_types.Part(inline_data=genai_types.Blob(data=image_b64, mime_type=mime_type)),
        ],
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def run_agent_to_text(
    agent: LlmAgent,
    prompt: str,
    app_name: str = "Hephae",
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
    app_name: str = "Hephae",
    state: dict | None = None,
    response_schema: type[BaseModel] | None = None,
) -> dict | list | BaseModel | None:
    """Run an agent, extract text, parse JSON, and optionally validate against Pydantic schema.

    Args:
        agent: The LlmAgent to run
        prompt: The user prompt to pass to the agent
        app_name: The app name for session management
        state: Optional session state
        response_schema: Optional Pydantic BaseModel class for native structured output.
            If provided, ADK will use this schema to constrain the LLM output to valid JSON
            matching the schema. The returned model instance will be automatically parsed
            and validated, eliminating manual JSON parsing.

    Returns:
        If response_schema is provided: a validated instance of the schema class
        Otherwise: a dict, list, or None (from manual JSON parsing)

    Example:
        # With native structured output:
        from hephae_db.schemas import ZipcodeScannerOutput
        result = await run_agent_to_json(
            agent, prompt, response_schema=ZipcodeScannerOutput
        )
        # result is now a ZipcodeScannerOutput instance, validated by Gemini

        # Without structured output (backward compatible):
        result = await run_agent_to_json(agent, prompt)
        # result is a dict parsed from JSON (old behavior)
    """
    if response_schema:
        # Native structured output path
        return await _run_agent_with_schema(agent, prompt, app_name, state, response_schema)
    else:
        # Backward-compatible JSON parsing path
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


async def _run_agent_with_schema(
    agent: LlmAgent,
    prompt: str,
    app_name: str,
    state: dict | None,
    response_schema: type[BaseModel],
) -> BaseModel | None:
    """Run an agent with native structured output via response_schema.

    This leverages ADK's native response_schema parameter to constrain the LLM
    to output JSON that matches the Pydantic schema. Gemini validates the schema
    automatically, eliminating parse errors.
    """
    session_id = f"{agent.name}-{uuid.uuid4().hex[:8]}"
    user_id = "system"

    # Create agent with response_schema parameter
    schema_agent = LlmAgent(
        name=agent.name,
        model=agent.model,
        instruction=agent.instruction,
        tools=agent.tools if hasattr(agent, "tools") else [],
        on_model_error_callback=agent.on_model_error_callback if hasattr(agent, "on_model_error_callback") else None,
        response_schema=response_schema,  # Native structured output
    )

    app = _get_or_create_app(schema_agent, app_name)

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

    if not last_text:
        logger.warning(f"[ADK] Agent {agent.name} returned empty output with schema")
        return None

    try:
        # Parse the JSON response into the Pydantic model
        parsed_json = json.loads(last_text)
        return response_schema(**parsed_json)
    except json.JSONDecodeError as e:
        logger.error(f"[ADK] Failed to parse JSON from {agent.name} with schema: {e}")
        logger.debug(f"[ADK] Raw output: {last_text[:500]}")
        return None
    except ValueError as e:
        # Pydantic validation error
        logger.error(f"[ADK] Schema validation failed for {agent.name}: {e}")
        logger.debug(f"[ADK] Raw output: {last_text[:500]}")
        return None
