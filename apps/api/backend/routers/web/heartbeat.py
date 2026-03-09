"""Heartbeat monitoring — user-facing CRUD for business watches."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.lib.auth import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["heartbeat"])

ALLOWED_CAPABILITIES = {"seo", "margin", "traffic", "competitive", "social"}


class CreateHeartbeatRequest(BaseModel):
    businessSlug: str
    businessName: str
    capabilities: list[str]  # ["seo", "margin", "traffic", "competitive", "social"]
    dayOfWeek: int = 1  # 0=Sun..6=Sat, default Monday


class UpdateHeartbeatRequest(BaseModel):
    capabilities: list[str] | None = None
    dayOfWeek: int | None = None
    active: bool | None = None


@router.post("/heartbeat")
async def create_heartbeat(
    req: CreateHeartbeatRequest,
    user: dict = Depends(verify_firebase_token),
):
    """Create a new heartbeat watch for a business."""
    from hephae_db.firestore.heartbeats import create_heartbeat as db_create

    invalid = set(req.capabilities) - ALLOWED_CAPABILITIES
    if invalid:
        raise HTTPException(400, f"Invalid capabilities: {invalid}")
    if not req.capabilities:
        raise HTTPException(400, "At least one capability required")

    heartbeat_id = await db_create(
        uid=user["uid"],
        business_slug=req.businessSlug,
        business_name=req.businessName,
        capabilities=req.capabilities,
        day_of_week=req.dayOfWeek,
    )
    return {"success": True, "id": heartbeat_id}


@router.get("/heartbeat")
async def list_heartbeats(user: dict = Depends(verify_firebase_token)):
    """List all heartbeats for the authenticated user."""
    from hephae_db.firestore.heartbeats import get_user_heartbeats

    heartbeats = await get_user_heartbeats(user["uid"])
    # Serialize timestamps
    for h in heartbeats:
        for field in ("createdAt", "lastRunAt", "nextRunAfter"):
            val = h.get(field)
            if val and hasattr(val, "isoformat"):
                h[field] = val.isoformat()
    return {"heartbeats": heartbeats}


@router.patch("/heartbeat/{heartbeat_id}")
async def update_heartbeat(
    heartbeat_id: str,
    req: UpdateHeartbeatRequest,
    user: dict = Depends(verify_firebase_token),
):
    """Update a heartbeat's capabilities, schedule, or active status."""
    from hephae_db.firestore.heartbeats import get_heartbeat, update_heartbeat as db_update

    hb = await get_heartbeat(heartbeat_id)
    if not hb or hb.get("uid") != user["uid"]:
        raise HTTPException(404, "Heartbeat not found")

    updates = {}
    if req.capabilities is not None:
        invalid = set(req.capabilities) - ALLOWED_CAPABILITIES
        if invalid:
            raise HTTPException(400, f"Invalid capabilities: {invalid}")
        updates["capabilities"] = req.capabilities
    if req.dayOfWeek is not None:
        updates["dayOfWeek"] = req.dayOfWeek
    if req.active is not None:
        updates["active"] = req.active

    if updates:
        await db_update(heartbeat_id, updates)
    return {"success": True}


@router.delete("/heartbeat/{heartbeat_id}")
async def delete_heartbeat(
    heartbeat_id: str,
    user: dict = Depends(verify_firebase_token),
):
    """Delete a heartbeat watch."""
    from hephae_db.firestore.heartbeats import get_heartbeat, delete_heartbeat as db_delete

    hb = await get_heartbeat(heartbeat_id)
    if not hb or hb.get("uid") != user["uid"]:
        raise HTTPException(404, "Heartbeat not found")
    await db_delete(heartbeat_id)
    return {"success": True}
