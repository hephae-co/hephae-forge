"""ADK Session Service backed by Firestore.

Allows agent session state to persist across multiple HTTP requests,
different agents, and human-in-the-loop gates.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from google.adk.sessions import Session, SessionService
from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "adk_sessions"

from datetime import datetime, timedelta
from typing import Any, List

from google.adk.sessions import Session, SessionService
from google.cloud.firestore import DELETE_FIELD
from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "adk_sessions"

# Heavy fields that should be pruned for long-term storage
HEAVY_FIELDS = ["rawSiteData", "markdown", "html", "screenshot_base64", "gemini_cache_name"]

class FirestoreSessionService(SessionService):
    """Native ADK SessionService implementation using Firestore with TTL support."""

    async def create_session(
        self, app_name: str, user_id: str, session_id: str, state: dict[str, Any]
    ) -> Session:
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(session_id)
        now = datetime.utcnow()

        # Strategy: Logged-in users get 30 days, guests get 24 hours
        is_guest = user_id in ("hub-user", "anonymous", "guest")
        ttl_days = 1 if is_guest else 30
        delete_at = now + timedelta(days=ttl_days)

        session = Session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=state,
        )

        data = {
            "appName": app_name,
            "userId": user_id,
            "state": state,
            "updatedAt": now,
            "deleteAt": delete_at, # Target field for Firestore TTL policy
            "isPermanent": not is_guest
        }

        await asyncio.to_thread(doc_ref.set, data)
        return session

    async def get_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> Session | None:
        db = get_db()
        doc = await asyncio.to_thread(db.collection(COLLECTION).document(session_id).get)

        if not doc.exists:
            return None

        data = doc.to_dict()
        return Session(
            app_name=data["appName"],
            user_id=data["userId"],
            session_id=session_id,
            state=data["state"],
        )

    async def update_session(
        self, app_name: str, user_id: str, session_id: str, state: dict[str, Any]
    ) -> Session:
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(session_id)

        # Merge state and refresh update timestamp
        await asyncio.to_thread(doc_ref.update, {
            "state": state,
            "updatedAt": datetime.utcnow()
        })

        return await self.get_session(app_name, user_id, session_id)

    async def prune_session(self, session_id: str):
        """Step 3: Remove heavy blobs to allow for cost-effective long-term persistence."""
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(session_id)

        updates = {}
        for field in HEAVY_FIELDS:
            updates[f"state.{field}"] = DELETE_FIELD

        if updates:
            logger.info(f"[SessionService] Pruning heavy fields from {session_id}")
            await asyncio.to_thread(doc_ref.update, updates)

    async def delete_session(self, app_name: str, user_id: str, session_id: str) -> None:
        db = get_db()
        await asyncio.to_thread(db.collection(COLLECTION).document(session_id).delete)

