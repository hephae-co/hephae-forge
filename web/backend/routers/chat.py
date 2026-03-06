"""POST /api/chat — Conversational chat with Gemini function calling."""

from __future__ import annotations

import json
import logging
import os

from google import genai
from google.genai import types
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.discovery import LocatorAgent
from backend.config import AgentModels
from backend.types import ChatResponse as ChatResponseModel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponseModel)
async def chat(request: Request):
    try:
        body = await request.json()
        messages = body.get("messages")
        context = body.get("context")

        if not messages or not isinstance(messages, list):
            return JSONResponse({"error": "Invalid messages array"}, status_code=400)

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse({"error": "Missing GEMINI_API_KEY"}, status_code=500)

        # Build context-aware system instruction
        system_instruction = (
            "You are Hephae, an intelligent assistant for business owners. "
            "Your primary capability is locating businesses and triggering deep-dives like Margin Analysis or Foot Traffic. "
            "If the user mentions a business, immediately use the `locate_business` tool to find its coordinates and URL. Be concise."
        )

        if context:
            parts = []
            if context.get("businessName"):
                parts.append(f"Business: {context['businessName']} ({context.get('address', 'address unknown')})")
            if context.get("seoReport"):
                parts.append(f"SEO Audit Results (score {context['seoReport'].get('overallScore', '?')}/100):\n{json.dumps(context['seoReport'], indent=1)}")
            if context.get("marginReport"):
                parts.append(f"Margin Analysis (score {context['marginReport'].get('overall_score', '?')}/100):\n{json.dumps(context['marginReport'], indent=1)}")
            if context.get("trafficForecast"):
                parts.append(f"Traffic Forecast:\n{json.dumps(context['trafficForecast'], indent=1)}")
            if context.get("competitiveReport"):
                parts.append(f"Competitive Analysis:\n{json.dumps(context['competitiveReport'], indent=1)}")

            if parts:
                system_instruction += (
                    "\n\nYou have the following analysis data for this business. Use it to answer questions "
                    "with specific numbers, data points, and actionable insights. Be direct, cite actual findings, "
                    'and use the "sassy advisor" tone -- highlight what\'s costing the owner money.\n\n'
                    + "\n\n".join(parts)
                )

        client = genai.Client(api_key=api_key)

        # Define the locate_business tool
        locate_tool = types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="locate_business",
                description="Resolves a conversational query for a business into canonical identity details.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="The search query (e.g. 'Bosphorus Nutley')",
                        ),
                    },
                    required=["query"],
                ),
            ),
        ])

        # Build chat history
        history = []
        for m in messages[:-1]:
            role = "user" if m.get("role") == "user" else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=m.get("text", ""))]))

        # Gemini requires first message to be from user
        while history and history[0].role == "model":
            history.pop(0)

        chat_session = client.chats.create(
            model=AgentModels.PRIMARY_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[locate_tool],
            ),
            history=history,
        )

        latest_message = messages[-1].get("text", "")
        response = chat_session.send_message(latest_message)

        # Check for function calls
        fc = None
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    fc = part.function_call
                    break

        if fc and fc.name == "locate_business":
            query_arg = fc.args.get("query", "")
            logger.info(f"[API/Chat] Model called locate_business with query: {query_arg}")

            try:
                identity = await LocatorAgent.resolve(query_arg)
                return JSONResponse({
                    "role": "model",
                    "text": f"I found **{identity['name']}** at {identity.get('address', 'unknown address')}. What would you like to do next?",
                    "triggerCapabilityHandoff": True,
                    "locatedBusiness": identity,
                })
            except Exception:
                return JSONResponse({
                    "role": "model",
                    "text": f'I couldn\'t locate "{query_arg}". Could you provide a bit more detail?',
                })

        return JSONResponse({
            "role": "model",
            "text": response.text,
        })

    except Exception as e:
        logger.error(f"[API/Chat] Failed: {e}")
        return JSONResponse({"error": str(e) or "Internal Server Error"}, status_code=500)
