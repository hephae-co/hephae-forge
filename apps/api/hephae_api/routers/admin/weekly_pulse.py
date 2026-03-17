"""Weekly Pulse admin endpoints — generate, view, and manage weekly briefings."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request
from hephae_api.routers.admin import _serialize
from hephae_db.firestore.weekly_pulse import (
    get_latest_pulse,
    get_pulse_by_id,
    get_pulse_history,
    list_pulses,
    delete_pulse,
)
from hephae_api.workflows.orchestrators.weekly_pulse import generate_pulse

router = APIRouter(
    prefix="/api/weekly-pulse",
    tags=["weekly-pulse"],
    dependencies=[Depends(verify_admin_request)],
)


class GeneratePulseRequest(BaseModel):
    zipCode: str
    businessType: str
    weekOf: str = ""
    force: bool = False


@router.post("")
async def generate_weekly_pulse(req: GeneratePulseRequest):
    """Generate a weekly pulse briefing for a zip code + business type."""
    if not re.match(r"^\d{5}$", req.zipCode):
        raise HTTPException(status_code=400, detail="Invalid zip code")
    if not req.businessType.strip():
        raise HTTPException(status_code=400, detail="businessType is required")

    result = await generate_pulse(
        zip_code=req.zipCode,
        business_type=req.businessType,
        week_of=req.weekOf,
        force=req.force,
    )
    return {
        "success": True,
        "pulse": _serialize(result["pulse"]),
        "pulseId": result["pulseId"],
        "signalsUsed": result["signalsUsed"],
    }


@router.get("")
async def list_all_pulses(limit: int = Query(20, ge=1, le=100)):
    """List all recent pulses across zip codes."""
    pulses = await list_pulses(limit=limit)
    return [_serialize(p) for p in pulses]


@router.get("/{zip_code}/{business_type}/latest")
async def get_latest(zip_code: str, business_type: str):
    """Get the most recent pulse for a zip code + business type."""
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    doc = await get_latest_pulse(zip_code, business_type)
    if not doc:
        raise HTTPException(status_code=404, detail="No pulse found")
    return _serialize(doc)


@router.get("/{zip_code}/{business_type}/history")
async def get_history(
    zip_code: str,
    business_type: str,
    limit: int = Query(8, ge=1, le=52),
):
    """Get historical pulses for a zip code + business type."""
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    docs = await get_pulse_history(zip_code, business_type, limit=limit)
    return [_serialize(d) for d in docs]


@router.get("/id/{pulse_id}")
async def get_by_id(pulse_id: str):
    """Get a specific pulse by its document ID."""
    doc = await get_pulse_by_id(pulse_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pulse not found")
    return _serialize(doc)


@router.delete("/id/{pulse_id}")
async def delete_pulse_endpoint(pulse_id: str):
    """Delete a specific pulse."""
    await delete_pulse(pulse_id)
    return {"success": True}
