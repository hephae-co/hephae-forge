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
    """Run an agent and return structured JSON using Gemini's native JSON mode.

    Constrains the LLM output to valid JSON, eliminating the need for manual 
    markdown fence stripping or regex hacks.
    """
    session_id = f"{agent.name}-{uuid.uuid4().hex[:8]}"
    user_id = "system"

    # P1.2: Dynamic Few-Shot Injection (The Flywheel)
    enriched_instruction = agent.instruction
    try:
        from hephae_db.eval.example_store import example_store
        enriched_instruction = await example_store.inject_examples_to_instruction(
            agent.name, prompt, agent.instruction
        )
    except Exception as e:
        logger.warning(f"[ADK] Example injection skipped for {agent.name}: {e}")

    # P0.3: Ensure Native JSON Mode is active
    schema_agent = LlmAgent(
        name=agent.name,
        model=agent.model,
        instruction=enriched_instruction,
        tools=agent.tools if hasattr(agent, "tools") else [],
        on_model_error_callback=agent.on_model_error_callback if hasattr(agent, "on_model_error_callback") else None,
        response_schema=response_schema,
        # Force native JSON mode even if no schema
        generate_content_config={"response_mime_type": "application/json"} if not response_schema else None,
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
        return None

    try:
        # P0.3: No more markdown stripping needed. last_text IS the JSON.
        parsed_json = json.loads(last_text)
        if response_schema:
            return response_schema(**parsed_json)
        return parsed_json
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"[ADK] Native JSON Mode failed for {agent.name}: {e}")
        logger.debug(f"[ADK] Raw output: {last_text[:500]}")
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
