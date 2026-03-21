"""POST /api/profile/build — Multi-turn profile building chat for authenticated users."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_firebase_token
from hephae_agents.profile_builder.agent import PROFILE_BUILDER_INSTRUCTION
from hephae_common.adk_helpers import user_msg
from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.report_storage import generate_slug
from hephae_db.firestore.session_service import FirestoreSessionService

logger = logging.getLogger(__name__)

router = APIRouter()

APP_NAME = "hephae-profile-builder"

_session_service = FirestoreSessionService()


def _make_save_profile_tool(result_holder: dict[str, Any]):
    """Create a save_profile tool that captures the collected profile data."""

    async def save_profile(
        social_profiles: dict[str, str] | None = None,
        delivery_apps: list[str] | None = None,
        menu_url: str | None = None,
        website_url: str | None = None,
        selected_capabilities: list[str] | None = None,
        tool_context: ToolContext | None = None,
    ) -> dict[str, Any]:
        """Save the business profile data collected from the user.

        Call this when you have gathered all the information from the user.

        Args:
            social_profiles: Dict of platform name to URL/handle (e.g., {"instagram": "https://instagram.com/mybiz"}).
            delivery_apps: List of delivery platform names (e.g., ["doordash", "ubereats"]).
            menu_url: Direct URL to the business menu with prices.
            website_url: The business website URL.
            selected_capabilities: List of capabilities to run (e.g., ["seo", "traffic", "competitive"]).

        Returns:
            Confirmation of saved profile.
        """
        profile = {
            "socialProfiles": social_profiles or {},
            "deliveryApps": delivery_apps or [],
            "menuUrl": menu_url or "",
            "websiteUrl": website_url or "",
            "selectedCapabilities": selected_capabilities or [],
        }
        result_holder["profile"] = profile
        result_holder["profileComplete"] = True

        cap_names = {
            "surgery": "Price Analysis",
            "margin": "Price Analysis",
            "traffic": "Foot Traffic Forecast",
            "seo": "SEO Audit",
            "competitive": "Competitor Breakdown",
            "marketing": "Social Media Audit",
            "social": "Social Media Audit",
        }
        selected = [cap_names.get(c, c) for c in (selected_capabilities or [])]

        return {
            "status": "saved",
            "message": f"Profile saved! Running: {', '.join(selected) if selected else 'no analyses selected'}.",
        }

    return save_profile


def _build_profile_agent(
    business_identity: dict[str, Any],
    save_tool: Any,
) -> LlmAgent:
    """Build the profile builder agent with business context."""
    instruction = PROFILE_BUILDER_INSTRUCTION

    # Inject known business info
    biz_info = f"\n\nBusiness info from initial search:\n- Name: {business_identity.get('name', 'Unknown')}"
    if business_identity.get("address"):
        biz_info += f"\n- Address: {business_identity['address']}"
    if business_identity.get("zipCode"):
        biz_info += f"\n- Zip Code: {business_identity['zipCode']}"
    if business_identity.get("officialUrl"):
        biz_info += f"\n- Website: {business_identity['officialUrl']}"
    if business_identity.get("phone"):
        biz_info += f"\n- Phone: {business_identity['phone']}"

    instruction += biz_info

    return LlmAgent(
        name="profile_builder",
        model=AgentModels.PRIMARY_MODEL,
        instruction=instruction,
        tools=[save_tool],
        on_model_error_callback=fallback_on_error,
    )


@router.post("/profile/build")
async def build_profile(request: Request, firebase_user: dict = Depends(verify_firebase_token)):
    """Multi-turn profile building chat. Requires Firebase authentication."""
    try:
        body = await request.json()
        messages = body.get("messages", [])
        business_identity = body.get("businessIdentity", {})
        session_id = body.get("sessionId")
        user_id = firebase_user.get("uid", "anonymous")

        if not messages or not isinstance(messages, list):
            return JSONResponse({"error": "Invalid messages array"}, status_code=400)

        latest_text = messages[-1].get("text", "")
        if not latest_text:
            return JSONResponse({"error": "Empty message"}, status_code=400)

        # Build agent with save_profile tool
        profile_result: dict[str, Any] = {}
        save_tool = _make_save_profile_tool(profile_result)
        agent = _build_profile_agent(business_identity, save_tool)

        # Get or create session
        session = None
        if session_id:
            session = await _session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

        if session is None:
            session = await _session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state={"businessIdentity": business_identity},
            )
            session_id = session.id

            # Replay prior messages if resuming
            if len(messages) > 1:
                from google.adk.events.event import Event
                from google.adk.events.event_actions import EventActions

                for m in messages[:-1]:
                    role = "user" if m.get("role") == "user" else "model"
                    event = Event(
                        author=role if role == "user" else "profile_builder",
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

        result: dict[str, Any] = {
            "role": "model",
            "text": response_text,
            "sessionId": session_id,
        }

        # If profile was completed (save_profile tool was called)
        if profile_result.get("profileComplete"):
            profile = profile_result["profile"]
            result["profileComplete"] = True
            result["profile"] = profile
            result["selectedCapabilities"] = profile.get("selectedCapabilities", [])

            # Save profile to Firestore
            slug = generate_slug(business_identity.get("name", "unknown"))
            asyncio.create_task(_save_profile_to_firestore(
                slug=slug,
                uid=user_id,
                business_identity=business_identity,
                profile=profile,
            ))

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"[API/ProfileBuilder] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e) or "Internal Server Error"}, status_code=500)


async def _save_profile_to_firestore(
    slug: str,
    uid: str,
    business_identity: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    """Save user-provided profile data to the businesses collection."""
    try:
        from hephae_common.firebase import get_db
        from hephae_db.firestore.users import add_business_to_user

        db = get_db()
        doc_ref = db.collection("businesses").document(slug)

        # Merge user-provided data with existing business data
        update_data: dict[str, Any] = {
            "name": business_identity.get("name", ""),
            "address": business_identity.get("address", ""),
            "zipCode": business_identity.get("zipCode", ""),
            "claimedBy": uid,
            "profileComplete": True,
        }

        if profile.get("socialProfiles"):
            update_data["socialLinks"] = profile["socialProfiles"]
        if profile.get("deliveryApps"):
            update_data["deliveryApps"] = profile["deliveryApps"]
        if profile.get("menuUrl"):
            update_data["menuUrl"] = profile["menuUrl"]
        if profile.get("websiteUrl"):
            update_data["officialUrl"] = profile["websiteUrl"]

        coords = business_identity.get("coordinates")
        if coords:
            update_data["coordinates"] = coords

        await asyncio.to_thread(doc_ref.set, update_data, merge=True)

        # Link business to user
        await asyncio.to_thread(add_business_to_user, uid, slug)

        logger.info(f"[ProfileBuilder] Saved profile for {slug}, user {uid}")

    except Exception as e:
        logger.error(f"[ProfileBuilder] Failed to save profile: {e}")
