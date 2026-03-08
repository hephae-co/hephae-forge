"""POST /api/chat — Conversational chat with ADK Agent + Firestore session persistence."""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from hephae_capabilities.discovery import LocatorAgent
from hephae_common.adk_helpers import user_msg
from hephae_common.model_config import AgentModels
from hephae_db.firestore.session_service import FirestoreSessionService

logger = logging.getLogger(__name__)

router = APIRouter()

APP_NAME = "hephae-chat"

# Singleton session service — shares Firestore client across requests
_session_service = FirestoreSessionService()

SYSTEM_INSTRUCTION = (
    "You are Hephae, an intelligent assistant for business owners. "
    "Your primary capability is locating businesses and triggering deep-dives like Margin Analysis or Foot Traffic. "
    "If the user mentions a business, immediately use the `locate_business` tool to find its coordinates and URL. Be concise."
)


async def locate_business(query: str, tool_context: ToolContext) -> dict[str, Any]:
    """Resolves a conversational query for a business into canonical identity details.

    Use this tool when the user mentions a specific business by name.

    Args:
        query: The search query (e.g. "Bosphorus Nutley").

    Returns:
        A dict with name, address, officialUrl, and coordinates.
    """
    identity = await LocatorAgent.resolve(query)
    # Persist in session state so the endpoint can read it back
    tool_context.state["temp:located_business"] = json.dumps(identity)
    return identity


def _build_chat_agent(context: dict[str, Any] | None = None) -> LlmAgent:
    """Build an ADK LlmAgent for the chat conversation.

    The system instruction is enriched with business context when available.
    """
    instruction = SYSTEM_INSTRUCTION

    if context:
        parts = []
        if context.get("businessName"):
            parts.append(
                f"Business: {context['businessName']} ({context.get('address', 'address unknown')})"
            )
        if context.get("seoReport"):
            parts.append(
                f"SEO Audit Results (score {context['seoReport'].get('overallScore', '?')}/100):\n"
                f"{json.dumps(context['seoReport'], indent=1)}"
            )
        if context.get("marginReport"):
            parts.append(
                f"Margin Analysis (score {context['marginReport'].get('overall_score', '?')}/100):\n"
                f"{json.dumps(context['marginReport'], indent=1)}"
            )
        if context.get("trafficForecast"):
            parts.append(f"Traffic Forecast:\n{json.dumps(context['trafficForecast'], indent=1)}")
        if context.get("competitiveReport"):
            parts.append(
                f"Competitive Analysis:\n{json.dumps(context['competitiveReport'], indent=1)}"
            )

        if parts:
            instruction += (
                "\n\nYou have the following analysis data for this business. Use it to answer questions "
                "with specific numbers, data points, and actionable insights. Be direct, cite actual findings, "
                'and use the "sassy advisor" tone -- highlight what\'s costing the owner money.\n\n'
                + "\n\n".join(parts)
            )

    return LlmAgent(
        name="hephae_chat",
        model=AgentModels.PRIMARY_MODEL,
        instruction=instruction,
        tools=[locate_business],
    )


@router.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages")
        context = body.get("context")
        session_id = body.get("sessionId")
        user_id = body.get("userId", "anonymous")

        if not messages or not isinstance(messages, list):
            return JSONResponse({"error": "Invalid messages array"}, status_code=400)

        latest_text = messages[-1].get("text", "")
        if not latest_text:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        # Build the agent (instruction depends on current context)
        agent = _build_chat_agent(context)

        # Get or create session
        session = None
        if session_id:
            session = await _session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

        if session is None:
            # Create new session — seed with history from client (migration support)
            session = await _session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state={},
            )
            session_id = session.id

            # If client sent prior history (pre-migration), replay it as events
            if len(messages) > 1:
                from google.adk.events.event import Event
                from google.adk.events.event_actions import EventActions

                for m in messages[:-1]:
                    role = "user" if m.get("role") == "user" else "model"
                    event = Event(
                        author=role if role == "user" else "hephae_chat",
                        content=types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=m.get("text", ""))],
                        ),
                        actions=EventActions(),
                    )
                    await _session_service.append_event(session, event)

        # Run the agent
        runner = Runner(
            app_name=APP_NAME,
            agent=agent,
            session_service=_session_service,
        )

        response_text = ""

        async for raw_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(latest_text),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts") and content.parts:
                for part in content.parts:
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        response_text += part.text

        # Check if locate_business was called (stored in temp state)
        located_business = None
        located_json = session.state.get("temp:located_business")
        if located_json:
            try:
                located_business = json.loads(located_json)
            except (json.JSONDecodeError, TypeError):
                pass

        result: dict[str, Any] = {
            "role": "model",
            "text": response_text,
            "sessionId": session_id,
        }

        if located_business:
            result["triggerCapabilityHandoff"] = True
            result["locatedBusiness"] = located_business

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"[API/Chat] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e) or "Internal Server Error"}, status_code=500)
