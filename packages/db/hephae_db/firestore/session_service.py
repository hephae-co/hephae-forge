"""ADK Session Service backed by Firestore.

Allows agent session state to persist across multiple HTTP requests,
different agents, and human-in-the-loop gates.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from google.adk.sessions import Session, BaseSessionService
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.cloud.firestore import DELETE_FIELD
from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "adk_sessions"

# Heavy fields that should be pruned for long-term storage
HEAVY_FIELDS = ["rawSiteData", "markdown", "html", "screenshot_base64", "gemini_cache_name"]

class FirestoreSessionService(BaseSessionService):
    """Native ADK SessionService implementation using Firestore with TTL support."""

    async def create_session(
        self, *, app_name: str, user_id: str, state: Optional[dict[str, Any]] = None, session_id: Optional[str] = None
    ) -> Session:
        import uuid
        sid = session_id or str(uuid.uuid4())
        state = state or {}

        db = get_db()
        doc_ref = db.collection(COLLECTION).document(sid)
        now = datetime.utcnow()

        # Strategy: Logged-in users get 30 days, guests get 24 hours
        is_guest = user_id in ("hub-user", "anonymous", "guest")
        ttl_days = 1 if is_guest else 30
        delete_at = now + timedelta(days=ttl_days)

        session = Session(
            id=sid,
            appName=app_name,
            userId=user_id,
            state=state,
        )

        data = {
            "appName": app_name,
            "userId": user_id,
            "state": state,
            "updatedAt": now,
            "deleteAt": delete_at,
            "isPermanent": not is_guest
        }

        await asyncio.to_thread(doc_ref.set, data)
        return session

    async def get_session(
        self, *, app_name: str, user_id: str, session_id: str, config: Any = None
    ) -> Session | None:
        db = get_db()
        doc = await asyncio.to_thread(db.collection(COLLECTION).document(session_id).get)

        if not doc.exists:
            return None

        data = doc.to_dict()
        return Session(
            id=session_id,
            appName=data["appName"],
            userId=data["userId"],
            state=data.get("state", {}),
        )

    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        db = get_db()
        query = db.collection(COLLECTION).where("appName", "==", app_name)
        if user_id:
            query = query.where("userId", "==", user_id)

        docs = await asyncio.to_thread(query.get)
        sessions = []
        for doc in docs:
            data = doc.to_dict()
            sessions.append(Session(
                id=doc.id,
                appName=data["appName"],
                userId=data["userId"],
                state=data.get("state", {}),
            ))
        return ListSessionsResponse(sessions=sessions)

    async def update_session(
        self, *, app_name: str, user_id: str, session_id: str, state: dict[str, Any]
    ) -> Session:
        """Custom method: merge state into an existing session."""
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(session_id)

        await asyncio.to_thread(doc_ref.update, {
            "state": state,
            "updatedAt": datetime.utcnow()
        })

        return await self.get_session(app_name=app_name, user_id=user_id, session_id=session_id)

    async def prune_session(self, session_id: str):
        """Remove heavy blobs to allow for cost-effective long-term persistence."""
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(session_id)

        updates = {}
        for field in HEAVY_FIELDS:
            updates[f"state.{field}"] = DELETE_FIELD

        if updates:
            logger.info(f"[SessionService] Pruning heavy fields from {session_id}")
            await asyncio.to_thread(doc_ref.update, updates)

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        db = get_db()
        await asyncio.to_thread(db.collection(COLLECTION).document(session_id).delete)
