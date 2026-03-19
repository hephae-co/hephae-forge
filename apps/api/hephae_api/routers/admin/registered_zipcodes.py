"""Registered Zipcodes admin endpoints — CRUD for weekly pulse onboarding.

POST   /api/registered-zipcodes                           — Register a new zipcode
GET    /api/registered-zipcodes                           — List all registered zipcodes
DELETE /api/registered-zipcodes/{zip_code}/{business_type} — Unregister
POST   /api/registered-zipcodes/{zip_code}/{business_type}/pause  — Pause
POST   /api/registered-zipcodes/{zip_code}/{business_type}/resume — Resume
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request
from hephae_api.routers.admin import _serialize

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/registered-zipcodes",
    tags=["registered-zipcodes"],
    dependencies=[Depends(verify_admin_request)],
)


class RegisterZipcodeRequest(BaseModel):
    zipCode: str
    businessType: str


@router.post("")
async def register_zipcode(req: RegisterZipcodeRequest):
    """Register a new zipcode + business type for weekly pulse generation."""
    if not re.match(r"^\d{5}$", req.zipCode):
        raise HTTPException(status_code=400, detail="Invalid zip code — must be 5 digits")
    if not req.businessType.strip():
        raise HTTPException(status_code=400, detail="businessType is required")

    from hephae_db.bigquery.public_data import resolve_zip_geography
    from hephae_db.firestore.registered_zipcodes import (
        get_registered_zipcode,
        register_zipcode as db_register,
    )

    # Check if already registered
    existing = await get_registered_zipcode(req.zipCode, req.businessType)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Already registered: {req.zipCode} / {req.businessType}",
        )

    # Resolve geography
    geo = await resolve_zip_geography(req.zipCode)
    if not geo:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve geography for zip code {req.zipCode}",
        )

    doc_id = await db_register(
        zip_code=req.zipCode,
        business_type=req.businessType,
        city=geo.city,
        state=geo.state_code,
        county=geo.county,
    )

    return {
        "success": True,
        "id": doc_id,
        "city": geo.city,
        "state": geo.state_code,
        "county": geo.county,
    }


@router.get("")
async def list_registered_zipcodes(status: str | None = Query(None)):
    """List all registered zipcodes, optionally filtered by status."""
    from hephae_db.firestore.registered_zipcodes import (
        list_registered_zipcodes as db_list,
    )

    if status and status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'paused'")

    docs = await db_list(status=status)
    return [_serialize(d) for d in docs]


@router.delete("/{zip_code}/{business_type}")
async def unregister_zipcode(zip_code: str, business_type: str):
    """Unregister a zipcode + business type from weekly pulse generation."""
    from hephae_db.firestore.registered_zipcodes import (
        get_registered_zipcode,
        unregister_zipcode as db_unregister,
    )

    existing = await get_registered_zipcode(zip_code, business_type)
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")

    await db_unregister(zip_code, business_type)
    return {"success": True}


@router.post("/{zip_code}/{business_type}/pause")
async def pause_zipcode(zip_code: str, business_type: str):
    """Pause weekly pulse generation for a zipcode."""
    from hephae_db.firestore.registered_zipcodes import (
        get_registered_zipcode,
        pause_zipcode as db_pause,
    )

    existing = await get_registered_zipcode(zip_code, business_type)
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    if existing.get("status") == "paused":
        raise HTTPException(status_code=400, detail="Already paused")

    await db_pause(zip_code, business_type)
    return {"success": True}


@router.post("/{zip_code}/{business_type}/resume")
async def resume_zipcode(zip_code: str, business_type: str):
    """Resume weekly pulse generation for a zipcode."""
    from hephae_db.firestore.registered_zipcodes import (
        get_registered_zipcode,
        resume_zipcode as db_resume,
    )

    existing = await get_registered_zipcode(zip_code, business_type)
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    if existing.get("status") == "active":
        raise HTTPException(status_code=400, detail="Already active")

    await db_resume(zip_code, business_type)
    return {"success": True}
