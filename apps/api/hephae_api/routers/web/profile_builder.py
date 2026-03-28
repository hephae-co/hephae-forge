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


# ---------------------------------------------------------------------------
# Section-level discovery endpoints — targeted crawl for individual sections
# ---------------------------------------------------------------------------


@router.post("/profile/discover")
async def discover_section(request: Request, firebase_user: dict = Depends(verify_firebase_token)):
    """Run a targeted crawl for a single profile section.

    Body: { "section": "menu"|"social"|"competitors"|"theme"|"contact",
            "identity": { name, address, zipCode, officialUrl, ... },
            "override": "optional manual input from user" }

    Returns the discovered data for that section only.
    """
    try:
        body = await request.json()
        section = body.get("section", "")
        identity = body.get("identity", {})
        override_value = body.get("override", "")

        if not section:
            return JSONResponse({"error": "Missing section"}, status_code=400)
        if not identity.get("name"):
            return JSONResponse({"error": "Missing identity.name"}, status_code=400)

        # If user provided a manual override, just save it directly
        if override_value:
            return JSONResponse({
                "section": section,
                "source": "user_input",
                "data": _build_override_data(section, override_value),
            })

        name = identity.get("name", "")
        url = identity.get("officialUrl", "")
        address = identity.get("address", "")
        logger.info(f"[ProfileDiscover] Section={section} for {name}")

        result = await _run_section_discovery(section, identity)

        return JSONResponse({
            "section": section,
            "source": "auto_discovered",
            "data": result,
        })

    except Exception as e:
        logger.error(f"[ProfileDiscover] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e) or "Discovery failed"}, status_code=500)


@router.post("/profile/confirm")
async def confirm_section(request: Request, firebase_user: dict = Depends(verify_firebase_token)):
    """Save user-confirmed or user-edited profile data for a section.

    Body: { "section": "menu"|"social"|..., "identity": {...}, "data": {...} }
    """
    try:
        body = await request.json()
        section = body.get("section", "")
        identity = body.get("identity", {})
        data = body.get("data", {})
        uid = firebase_user.get("uid", "anonymous")

        if not section or not identity.get("name"):
            return JSONResponse({"error": "Missing section or identity"}, status_code=400)

        slug = generate_slug(identity.get("name", "unknown"))
        await _save_section_to_firestore(slug, uid, section, data, identity)

        return JSONResponse({"status": "saved", "section": section, "slug": slug})

    except Exception as e:
        logger.error(f"[ProfileConfirm] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e) or "Save failed"}, status_code=500)


def _build_override_data(section: str, value: str) -> dict[str, Any]:
    """Build structured data from a user's manual input for a section."""
    if section == "menu":
        return {"menuUrl": value}
    elif section == "social":
        # Try to detect platform from URL
        v = value.lower()
        if "instagram" in v:
            return {"instagram": value}
        elif "facebook" in v:
            return {"facebook": value}
        elif "tiktok" in v:
            return {"tiktok": value}
        elif "yelp" in v:
            return {"yelp": value}
        elif "twitter" in v or "x.com" in v:
            return {"twitter": value}
        return {"url": value}
    elif section == "competitors":
        return {"competitors": [{"name": value, "url": "", "reason": "User-provided"}]}
    elif section == "theme":
        return {"websiteUrl": value}
    elif section == "contact":
        if "@" in value:
            return {"email": value}
        return {"phone": value}
    return {"value": value}


async def _run_section_discovery(section: str, identity: dict[str, Any]) -> dict[str, Any]:
    """Run a single discovery agent for the requested section."""
    import uuid
    from google.adk.runners import Runner, RunConfig
    from google.adk.sessions import InMemorySessionService

    name = identity.get("name", "")
    url = identity.get("officialUrl", "")
    address = identity.get("address", "")
    zip_code = identity.get("zipCode", "")

    session_service = InMemorySessionService()
    session_id = f"discover-{section}-{uuid.uuid4().hex[:8]}"

    # Build section-specific agent and prompt
    agent, prompt, initial_state = _build_section_agent(section, identity)

    session = await session_service.create_session(
        app_name="profile-discover",
        user_id="system",
        session_id=session_id,
        state=initial_state,
    )

    runner = Runner(
        agent=agent,
        app_name="profile-discover",
        session_service=session_service,
    )

    # Menu/theme need more calls (crawl → follow links → extract)
    max_calls = 15 if section in ("menu", "theme") else 8

    last_text = ""
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_msg(prompt),
        run_config=RunConfig(max_llm_calls=max_calls),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    last_text = part.text

    # Also check session state for output_key results
    final_session = await session_service.get_session(
        app_name="profile-discover",
        user_id="system",
        session_id=session_id,
    )
    state = dict(final_session.state) if final_session and final_session.state else {}

    # Extract the relevant output
    output_key = {
        "menu": "menuData",
        "social": "socialData",
        "competitors": "competitorData",
        "theme": "themeData",
        "contact": "contactData",
    }.get(section, section + "Data")

    result = state.get(output_key)
    if result:
        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return {"raw": result}
        return result

    # Fallback: try parsing last_text as JSON
    if last_text:
        try:
            return json.loads(last_text)
        except (json.JSONDecodeError, ValueError):
            return {"raw": last_text[:500]}

    return {}


def _build_section_agent(section: str, identity: dict[str, Any]) -> tuple:
    """Build agent, prompt, and initial state for a specific section discovery."""
    from google.adk.agents import LlmAgent
    from google.adk.tools import google_search

    from hephae_agents.shared_tools import (
        playwright_tool,
        crawl4ai_tool,
        crawl4ai_advanced_tool,
        crawl4ai_deep_tool,
    )
    from hephae_agents.discovery.prompts import (
        MENU_AGENT_INSTRUCTION,
        SOCIAL_MEDIA_AGENT_INSTRUCTION,
        COMPETITOR_AGENT_INSTRUCTION,
        SITE_CRAWLER_INSTRUCTION,
        CONTACT_AGENT_INSTRUCTION,
    )

    name = identity.get("name", "")
    url = identity.get("officialUrl", "")
    address = identity.get("address", "")

    # google_search (built-in server-side tool) CANNOT be mixed with custom
    # function tools in the same agent — current SDK doesn't support
    # include_server_side_tool_invocations. Use one type per agent.

    if section == "menu":
        # Crawl tools only — search the business website + delivery platforms
        agent = LlmAgent(
            name="menu_discover",
            model=AgentModels.PRIMARY_MODEL,
            instruction=MENU_AGENT_INSTRUCTION,
            tools=[playwright_tool, crawl4ai_advanced_tool],
            output_key="menuData",
            on_model_error_callback=fallback_on_error,
        )
        prompt = f"Find the menu with prices for: {name}\nWebsite: {url}\nAddress: {address}\nAlso check delivery platforms (DoorDash, Grubhub, UberEats)."
        return agent, prompt, {}

    elif section == "social":
        # google_search only
        agent = LlmAgent(
            name="social_discover",
            model=AgentModels.PRIMARY_MODEL,
            instruction=SOCIAL_MEDIA_AGENT_INSTRUCTION,
            tools=[google_search],
            output_key="socialData",
            on_model_error_callback=fallback_on_error,
        )
        prompt = f"Find all social media profiles for: {name}\nWebsite: {url}\nAddress: {address}\nSearch Instagram, Facebook, TikTok, Yelp, Twitter/X."
        return agent, prompt, {}

    elif section == "competitors":
        # google_search only — find competitors via search
        agent = LlmAgent(
            name="competitor_discover",
            model=AgentModels.PRIMARY_MODEL,
            instruction=COMPETITOR_AGENT_INSTRUCTION,
            tools=[google_search],
            output_key="competitorData",
            on_model_error_callback=fallback_on_error,
        )
        prompt = f"Find 3 direct competitors for: {name}\nAddress: {address}\nFor each, provide name, website URL, and why they compete."
        return agent, prompt, {}

    elif section == "theme":
        # Crawl tools only
        agent = LlmAgent(
            name="theme_discover",
            model=AgentModels.PRIMARY_MODEL,
            instruction=SITE_CRAWLER_INSTRUCTION,
            tools=[playwright_tool, crawl4ai_tool, crawl4ai_advanced_tool],
            output_key="rawSiteData",
            on_model_error_callback=fallback_on_error,
        )
        prompt = f"Crawl the website for {name}: {url}\nExtract logo, favicon, brand colors, and business persona."
        return agent, prompt, {}

    elif section == "contact":
        # google_search only — find contact info from listings
        agent = LlmAgent(
            name="contact_discover",
            model=AgentModels.PRIMARY_MODEL,
            instruction=CONTACT_AGENT_INSTRUCTION,
            tools=[google_search],
            output_key="contactData",
            on_model_error_callback=fallback_on_error,
        )
        prompt = f"Find contact details for: {name}\nWebsite: {url}\nAddress: {address}\nFind email, phone, hours, contact form."
        return agent, prompt, {}

    else:
        raise ValueError(f"Unknown section: {section}")


async def _save_section_to_firestore(
    slug: str,
    uid: str,
    section: str,
    data: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    """Save confirmed section data to Firestore."""
    try:
        from hephae_common.firebase import get_db

        db = get_db()
        doc_ref = db.collection("businesses").document(slug)

        update: dict[str, Any] = {
            "name": identity.get("name", ""),
            "lastUpdatedBy": uid,
        }

        if section == "menu":
            if data.get("menuUrl"):
                update["menuUrl"] = data["menuUrl"]
            for platform in ("grubhub", "doordash", "ubereats", "seamless", "toasttab"):
                if data.get(platform):
                    update[f"deliveryLinks.{platform}"] = data[platform]
        elif section == "social":
            for platform in ("instagram", "facebook", "twitter", "tiktok", "yelp"):
                if data.get(platform):
                    update[f"socialLinks.{platform}"] = data[platform]
        elif section == "competitors":
            comps = data.get("competitors", data if isinstance(data, list) else [])
            if comps:
                update["competitors"] = comps[:5]
        elif section == "theme":
            for key in ("logoUrl", "favicon", "primaryColor", "secondaryColor", "persona"):
                if data.get(key):
                    update[key] = data[key]
        elif section == "contact":
            for key in ("email", "phone", "hours", "contactFormUrl"):
                if data.get(key):
                    update[key] = data[key]

        await asyncio.to_thread(doc_ref.set, update, merge=True)
        logger.info(f"[ProfileConfirm] Saved {section} for {slug}, user {uid}")

    except Exception as e:
        logger.error(f"[ProfileConfirm] Failed to save {section}: {e}")


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
