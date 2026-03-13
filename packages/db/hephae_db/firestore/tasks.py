"""Firestore CRUD for the tasks collection.

Tasks track individual agentic actions (Enrich, Analyze, Outreach)
triggered either by manual UI selection or batch jobs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "tasks"

# Task Statuses
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

async def create_task(
    business_id: str,
    action_type: str,
    triggered_by: str = "admin",
    priority: int = 5,
    metadata: dict[str, Any] | None = None
) -> str:
    """Create a new background task record."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    
    task_data = {
        "businessId": business_id,
        "actionType": action_type,
        "status": STATUS_QUEUED,
        "progress": 0,
        "triggeredBy": triggered_by,
        "priority": priority,
        "createdAt": datetime.utcnow(),
        "startedAt": None,
        "completedAt": None,
        "metadata": metadata or {},
        "error": None
    }
    
    await asyncio.to_thread(doc_ref.set, task_data)
    return doc_ref.id

async def update_task(task_id: str, updates: dict[str, Any]):
    """Update task progress or status."""
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(task_id).update, updates)

async def get_task(task_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(task_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data

async def get_tasks_by_ids(task_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch multiple task documents by their IDs (batched for efficiency)."""
    if not task_ids:
        return []

    db = get_db()
    tasks = []

    # Firestore getAll supports up to 500 docs per batch
    for i in range(0, len(task_ids), 100):
        batch_ids = task_ids[i : i + 100]
        refs = [db.collection(COLLECTION).document(tid) for tid in batch_ids]
        docs = await asyncio.to_thread(lambda: list(db.get_all(refs)))
        for doc in docs:
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                tasks.append(data)

    return tasks


async def list_active_tasks_for_businesses(business_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch the most recent active tasks for a set of businesses."""
    if not business_ids:
        return []
    
    db = get_db()
    # Firestore 'in' query is limited to 30 items
    tasks = []
    for i in range(0, len(business_ids), 30):
        batch = business_ids[i:i+30]
        docs = await asyncio.to_thread(
            lambda: db.collection(COLLECTION)
            .where("businessId", "in", batch)
            .order_by("createdAt", direction="DESCENDING")
            .limit(100) # Get a reasonable history
            .get()
        )
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            tasks.append(d)
            
    return tasks
