"""Firestore-backed ADK SessionService.

Persists ADK sessions, events, and state scopes to Firestore.

Collection layout:
  adk_sessions/{session_id}              — session metadata + session-scoped state
  adk_sessions/{session_id}/events/{eid} — individual Event documents (no growing arrays)
  adk_app_state/{app_name}               — app-scoped state (shared across all users)
  adk_user_state/{app_name}___{user_id}  — user-scoped state (shared across sessions)
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any, Optional

import uuid

from google.adk.events.event import Event
from google.adk.sessions import _session_util
from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)
from google.adk.sessions.session import Session
from google.adk.sessions.state import State
from google.cloud.firestore_v1.base_query import FieldFilter
from typing_extensions import override

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

# Firestore collection names
_SESSIONS_COL = "adk_sessions"
_EVENTS_SUBCOL = "events"
_APP_STATE_COL = "adk_app_state"
_USER_STATE_COL = "adk_user_state"


def _user_state_doc_id(app_name: str, user_id: str) -> str:
    return f"{app_name}___{user_id}"


def _session_to_doc(session: Session) -> dict[str, Any]:
    """Convert a Session to a Firestore-safe document dict (no events)."""
    return {
        "app_name": session.app_name,
        "user_id": session.user_id,
        "state": session.state if isinstance(session.state, dict) else session.state.to_dict(),
        "last_update_time": session.last_update_time,
    }


def _event_to_doc(event: Event) -> dict[str, Any]:
    """Serialize an Event to a Firestore-safe dict via Pydantic JSON."""
    return event.model_dump(mode="json", by_alias=True)


def _doc_to_event(data: dict[str, Any]) -> Event:
    """Deserialize a Firestore doc back to an Event."""
    return Event.model_validate(data)


class FirestoreSessionService(BaseSessionService):
    """ADK SessionService backed by Firestore.

    Uses ``asyncio.to_thread`` to wrap the synchronous Firestore client,
    matching the pattern used throughout hephae-db.
    """

    # ------------------------------------------------------------------
    # create_session
    # ------------------------------------------------------------------
    @override
    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = (
            session_id.strip()
            if session_id and session_id.strip()
            else str(uuid.uuid4())
        )

        # Separate state scopes
        state_deltas = _session_util.extract_state_delta(state or {})
        app_state_delta = state_deltas["app"]
        user_state_delta = state_deltas["user"]
        session_state = state_deltas["session"]

        now = time.time()
        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=session_state,
            last_update_time=now,
        )

        db = get_db()

        def _write() -> None:
            batch = db.batch()

            # Session document
            batch.set(
                db.collection(_SESSIONS_COL).document(session_id),
                _session_to_doc(session),
            )

            # App state
            if app_state_delta:
                batch.set(
                    db.collection(_APP_STATE_COL).document(app_name),
                    app_state_delta,
                    merge=True,
                )

            # User state
            if user_state_delta:
                batch.set(
                    db.collection(_USER_STATE_COL).document(
                        _user_state_doc_id(app_name, user_id)
                    ),
                    user_state_delta,
                    merge=True,
                )

            batch.commit()

        await asyncio.to_thread(_write)

        # Return a copy with merged scoped state
        return await self._merge_state(app_name, user_id, copy.deepcopy(session))

    # ------------------------------------------------------------------
    # get_session
    # ------------------------------------------------------------------
    @override
    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        db = get_db()

        def _read_session() -> Optional[dict[str, Any]]:
            doc = db.collection(_SESSIONS_COL).document(session_id).get()
            return doc.to_dict() if doc.exists else None

        doc_data = await asyncio.to_thread(_read_session)
        if doc_data is None:
            return None

        # Verify app_name and user_id match
        if doc_data.get("app_name") != app_name or doc_data.get("user_id") != user_id:
            return None

        session = Session(
            app_name=app_name,
            user_id=user_id,
            id=session_id,
            state=doc_data.get("state", {}),
            last_update_time=doc_data.get("last_update_time", 0.0),
        )

        # Load events from subcollection
        def _read_events() -> list[dict[str, Any]]:
            events_ref = (
                db.collection(_SESSIONS_COL)
                .document(session_id)
                .collection(_EVENTS_SUBCOL)
                .order_by("timestamp")
            )
            return [doc.to_dict() for doc in events_ref.stream()]

        event_docs = await asyncio.to_thread(_read_events)
        events = [_doc_to_event(d) for d in event_docs]

        # Apply config filters
        if config:
            if config.after_timestamp:
                events = [e for e in events if e.timestamp >= config.after_timestamp]
            if config.num_recent_events:
                events = events[-config.num_recent_events:]

        session.events = events

        return await self._merge_state(app_name, user_id, session)

    # ------------------------------------------------------------------
    # list_sessions
    # ------------------------------------------------------------------
    @override
    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        db = get_db()

        def _query() -> list[tuple[str, dict[str, Any]]]:
            query = db.collection(_SESSIONS_COL).where(
                filter=FieldFilter("app_name", "==", app_name)
            )
            if user_id is not None:
                query = query.where(
                    filter=FieldFilter("user_id", "==", user_id)
                )
            return [(doc.id, doc.to_dict()) for doc in query.stream()]

        results = await asyncio.to_thread(_query)

        sessions = []
        for doc_id, data in results:
            s = Session(
                app_name=app_name,
                user_id=data.get("user_id", ""),
                id=doc_id,
                state=data.get("state", {}),
                last_update_time=data.get("last_update_time", 0.0),
            )
            # list_sessions returns sessions without events
            sessions.append(s)

        return ListSessionsResponse(sessions=sessions)

    # ------------------------------------------------------------------
    # delete_session
    # ------------------------------------------------------------------
    @override
    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        db = get_db()

        def _delete() -> None:
            session_ref = db.collection(_SESSIONS_COL).document(session_id)

            # Delete all events in the subcollection first
            events_ref = session_ref.collection(_EVENTS_SUBCOL)
            batch = db.batch()
            count = 0
            for event_doc in events_ref.stream():
                batch.delete(event_doc.reference)
                count += 1
                # Firestore batch limit is 500
                if count >= 450:
                    batch.commit()
                    batch = db.batch()
                    count = 0
            if count > 0:
                batch.commit()

            # Delete the session document
            session_ref.delete()

        await asyncio.to_thread(_delete)

    # ------------------------------------------------------------------
    # append_event
    # ------------------------------------------------------------------
    @override
    async def append_event(self, session: Session, event: Event) -> Event:
        if event.partial:
            return event

        # Let the base class update in-memory session state
        await super().append_event(session=session, event=event)
        session.last_update_time = event.timestamp

        db = get_db()
        session_id = session.id
        app_name = session.app_name
        user_id = session.user_id

        # Extract state deltas for scoped persistence
        state_delta = (
            event.actions.state_delta
            if event.actions and event.actions.state_delta
            else {}
        )
        state_deltas = _session_util.extract_state_delta(state_delta)

        def _persist() -> None:
            batch = db.batch()

            # Write event to subcollection
            event_ref = (
                db.collection(_SESSIONS_COL)
                .document(session_id)
                .collection(_EVENTS_SUBCOL)
                .document(event.id)
            )
            batch.set(event_ref, _event_to_doc(event))

            # Update session metadata (state + last_update_time)
            session_ref = db.collection(_SESSIONS_COL).document(session_id)
            session_update: dict[str, Any] = {
                "last_update_time": event.timestamp,
            }
            # Persist session-scoped state delta
            session_state_delta = state_deltas["session"]
            if session_state_delta:
                for key, value in session_state_delta.items():
                    session_update[f"state.{key}"] = value
            batch.update(session_ref, session_update)

            # App state
            if state_deltas["app"]:
                batch.set(
                    db.collection(_APP_STATE_COL).document(app_name),
                    state_deltas["app"],
                    merge=True,
                )

            # User state
            if state_deltas["user"]:
                batch.set(
                    db.collection(_USER_STATE_COL).document(
                        _user_state_doc_id(app_name, user_id)
                    ),
                    state_deltas["user"],
                    merge=True,
                )

            batch.commit()

        await asyncio.to_thread(_persist)
        return event

    # ------------------------------------------------------------------
    # _merge_state (helper)
    # ------------------------------------------------------------------
    async def _merge_state(
        self, app_name: str, user_id: str, session: Session
    ) -> Session:
        """Merge app-scoped and user-scoped state into the session's state dict."""
        db = get_db()

        def _read_scoped_state() -> tuple[dict[str, Any], dict[str, Any]]:
            app_doc = db.collection(_APP_STATE_COL).document(app_name).get()
            app_state = app_doc.to_dict() or {} if app_doc.exists else {}

            user_doc = (
                db.collection(_USER_STATE_COL)
                .document(_user_state_doc_id(app_name, user_id))
                .get()
            )
            user_state = user_doc.to_dict() or {} if user_doc.exists else {}

            return app_state, user_state

        app_state, user_state = await asyncio.to_thread(_read_scoped_state)

        for key, value in app_state.items():
            session.state[State.APP_PREFIX + key] = value
        for key, value in user_state.items():
            session.state[State.USER_PREFIX + key] = value

        return session
