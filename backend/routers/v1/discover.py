"""POST /api/v1/discover — Headless full discovery (locate + pipeline + persist)."""

from __future__ import annotations

import logging
import re
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.discovery import LocatorAgent, discovery_pipeline
from backend.lib.firebase import db
from backend.lib.adk_helpers import user_msg
from backend.types import EnrichedProfile, V1Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/discover", response_model=V1Response[EnrichedProfile])
async def v1_discover(request: Request):
    try:
        body = await request.json()
        query = body.get("query")

        if not query or not isinstance(query, str):
            return JSONResponse({"error": "Missing or invalid 'query' parameter."}, status_code=400)

        logger.info(f'[V1/Discover] Starting Full Headless Discovery for: "{query}"')

        # Phase 1: Locate Business
        logger.info("[V1/Discover] Step 1: Resolving Base Identity via LocatorAgent...")
        try:
            base_identity = await LocatorAgent.resolve(query)
            logger.info(f"[V1/Discover]     -> Found: {base_identity.get('name')} at {base_identity.get('address')}")
        except Exception:
            return JSONResponse(
                {"error": f"Could not locate business matching query: {query}"},
                status_code=404,
            )

        # Phase 2: Discovery Pipeline
        logger.info("[V1/Discover] Step 2: Running DiscoveryPipeline...")
        session_service = InMemorySessionService()
        runner = Runner(app_name="hephae-hub", agent=discovery_pipeline, session_service=session_service)
        session_id = f"discovery-v1-{int(time.time() * 1000)}"
        user_id = "api-v1-client"

        await session_service.create_session(
            app_name="hephae-hub", user_id=user_id, session_id=session_id, state={}
        )

        prompt = (
            f"Please discover everything about this business:\n"
            f"Name: {base_identity.get('name', '')}\n"
            f"Address: {base_identity.get('address', '')}\n"
            f"URL: {base_identity.get('officialUrl', '')}"
        )

        event_count = 0
        async for _ in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            event_count += 1

        final_session = await session_service.get_session(
            app_name="hephae-hub", user_id=user_id, session_id=session_id
        )
        state = final_session.state if final_session else {}

        logger.info(f"[V1/Discover]     -> Pipeline completed ({event_count} ticks). Formatting Payload...")

        enriched_profile = {**base_identity, **state}

        # Phase 3: Firebase Persistence
        try:
            logger.info("[V1/Discover] Step 3: Pushing Enriched Profile to Firestore 'discovered_businesses'...")
            name = base_identity.get("name", "")
            address = base_identity.get("address", "")
            doc_id = re.sub(r"[^a-zA-Z0-9]", "_", name).lower() + "_" + re.sub(
                r"[^a-zA-Z0-9]", "", address
            )[:10]

            from datetime import datetime

            db_ref = db.collection("discovered_businesses").document(doc_id)
            db_ref.set({**enriched_profile, "last_discovered_at": datetime.utcnow()}, merge=True)
            logger.info(f"[V1/Discover]     -> Successfully saved to Document ID: {doc_id}")
        except Exception as db_err:
            logger.error(
                f"[V1/Discover] Failed to write to Firestore DB, but returning payload anyway: {db_err}"
            )

        return JSONResponse({"success": True, "data": enriched_profile})

    except Exception as exc:
        logger.error(f"[V1/Discover] Fatal API Error: {exc}")
        return JSONResponse({"error": str(exc) or "Internal Server Error"}, status_code=500)
