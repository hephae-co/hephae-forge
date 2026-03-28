"""Firestore-backed ADK MemoryService — persistent per-user long-term memory.

Stores conversation summaries and key facts per user in Firestore.
Agents can search past interactions via keyword matching.

Collection: agent_memory
Document ID: {app_name}_{user_id}_{session_id}
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from google.adk.events import Event
from google.adk.memory import BaseMemoryService
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.sessions import Session
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

COLLECTION = "agent_memory"
_MAX_MEMORIES_PER_USER = 200  # cap to prevent unbounded growth


def _user_key(app_name: str, user_id: str) -> str:
    return f"{app_name}_{user_id}"


def _extract_text(content: Content | None) -> str:
    """Extract plain text from a Content object."""
    if not content or not content.parts:
        return ""
    return " ".join(
        p.text for p in content.parts if hasattr(p, "text") and p.text
    )


class FirestoreMemoryService(BaseMemoryService):
    """Persistent memory service backed by Firestore.

    Each user gets a subcollection under agent_memory/{user_key}/entries.
    Memory entries are conversation turns stored as text for keyword search.
    """

    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            from hephae_common.firebase import get_db
            self._db = get_db()
        return self._db

    def _entries_ref(self, app_name: str, user_id: str):
        db = self._get_db()
        user_key = _user_key(app_name, user_id)
        return db.collection(COLLECTION).document(user_key).collection("entries")

    async def add_session_to_memory(self, session: Session) -> None:
        """Store all events from a completed session as memory entries."""
        if not session.events:
            return

        entries_ref = self._entries_ref(session.app_name, session.user_id)

        batch_data = []
        for event in session.events:
            text = _extract_text(event.content)
            if not text or len(text) < 10:
                continue
            author = getattr(event, "author", "unknown")
            batch_data.append({
                "sessionId": session.id,
                "author": author,
                "text": text[:2000],  # cap individual entries
                "createdAt": datetime.now(timezone.utc),
            })

        if not batch_data:
            return

        # Write in a Firestore batch
        db = self._get_db()
        batch = db.batch()
        for entry in batch_data[-20:]:  # keep last 20 turns per session
            doc_ref = entries_ref.document()
            batch.set(doc_ref, entry)

        await asyncio.to_thread(batch.commit)
        logger.info(
            f"[FirestoreMemory] Stored {len(batch_data)} entries for "
            f"{session.app_name}/{session.user_id}/{session.id}"
        )

    async def add_events_to_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        events: Sequence[Event],
        session_id: str | None = None,
        custom_metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Add individual events to memory."""
        entries_ref = self._entries_ref(app_name, user_id)
        db = self._get_db()
        batch = db.batch()
        count = 0

        for event in events:
            text = _extract_text(event.content)
            if not text or len(text) < 10:
                continue
            author = getattr(event, "author", "unknown")
            doc_ref = entries_ref.document()
            batch.set(doc_ref, {
                "sessionId": session_id or "unknown",
                "author": author,
                "text": text[:2000],
                "createdAt": datetime.now(timezone.utc),
            })
            count += 1

        if count > 0:
            await asyncio.to_thread(batch.commit)
            logger.info(f"[FirestoreMemory] Added {count} events for {app_name}/{user_id}")

    async def add_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        memories: Sequence[MemoryEntry],
        custom_metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Add explicit memory entries (e.g., user preferences, business facts)."""
        entries_ref = self._entries_ref(app_name, user_id)
        db = self._get_db()
        batch = db.batch()

        for mem in memories:
            text = _extract_text(mem.content) if mem.content else ""
            if not text:
                continue
            doc_ref = entries_ref.document()
            batch.set(doc_ref, {
                "sessionId": "explicit",
                "author": "system",
                "text": text[:2000],
                "createdAt": datetime.now(timezone.utc),
            })

        await asyncio.to_thread(batch.commit)
        logger.info(f"[FirestoreMemory] Added {len(memories)} explicit memories for {app_name}/{user_id}")

    async def search_memory(
        self,
        *,
        app_name: str,
        user_id: str,
        query: str,
    ):
        """Search past memory entries by keyword matching.

        Returns a SearchMemoryResponse with matching entries.
        """
        from google.adk.memory.base_memory_service import SearchMemoryResponse

        entries_ref = self._entries_ref(app_name, user_id)

        # Fetch recent entries (Firestore doesn't support full-text search,
        # so we fetch recent entries and filter client-side)
        docs = await asyncio.to_thread(
            entries_ref.order_by("createdAt", direction="DESCENDING")
            .limit(_MAX_MEMORIES_PER_USER)
            .get
        )

        # Keyword matching (same approach as InMemoryMemoryService)
        query_words = set(re.sub(r"[^\w\s]", "", query.lower()).split())
        if not query_words:
            return SearchMemoryResponse(memories=[])

        scored: list[tuple[float, dict]] = []
        for doc in docs:
            data = doc.to_dict()
            text = data.get("text", "")
            text_words = set(re.sub(r"[^\w\s]", "", text.lower()).split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                scored.append((score, data))

        # Sort by relevance, return top 10
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:10]

        memories = []
        for score, data in top:
            memories.append(MemoryEntry(
                content=Content(
                    role="user" if data.get("author") == "user" else "model",
                    parts=[Part.from_text(text=data["text"])],
                ),
            ))

        return SearchMemoryResponse(memories=memories)
