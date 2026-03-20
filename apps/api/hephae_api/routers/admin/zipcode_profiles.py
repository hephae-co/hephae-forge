"""Zipcode Profile admin endpoints — discover, view, list, delete, refresh.

POST   /api/zipcode-profiles/discover/{zip_code}  — Trigger full discovery
GET    /api/zipcode-profiles/{zip_code}            — View profile
GET    /api/zipcode-profiles                       — List all profiles
DELETE /api/zipcode-profiles/{zip_code}            — Delete profile
POST   /api/zipcode-profiles/{zip_code}/refresh    — Re-run discovery
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from hephae_api.lib.auth import verify_admin_request
from hephae_api.routers.admin import _serialize

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/zipcode-profiles",
    tags=["zipcode-profiles"],
    dependencies=[Depends(verify_admin_request)],
)


@router.post("/discover/{zip_code}")
async def discover_zipcode_profile(zip_code: str):
    """Trigger full two-phase discovery for a zip code.

    Runs synchronously (~60-90s) — within Cloud Run 5-min timeout.
    """
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code — must be 5 digits")

    from hephae_agents.research.zipcode_profile_discovery import (
        run_zipcode_profile_discovery,
    )

    logger.info(f"[ZipcodeProfiles] Starting discovery for {zip_code}")
    try:
        profile = await run_zipcode_profile_discovery(zip_code)
    except Exception as e:
        logger.error(f"[ZipcodeProfiles] Discovery failed for {zip_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {e}")

    if profile.get("error"):
        raise HTTPException(status_code=404, detail=profile["error"])

    return {
        "success": True,
        "zipCode": zip_code,
        "confirmedSources": profile.get("confirmedSources", 0),
        "unavailableSources": profile.get("unavailableSources", 0),
        "profile": _serialize(profile),
    }


@router.get("/{zip_code}")
async def get_zipcode_profile(zip_code: str):
    """View a single zipcode profile."""
    from hephae_db.firestore.zipcode_profiles import (
        get_zipcode_profile as db_get,
    )

    profile = await db_get(zip_code)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile found for {zip_code}")

    return _serialize(profile)


@router.get("")
async def list_zipcode_profiles():
    """List all discovered zipcode profiles."""
    from hephae_db.firestore.zipcode_profiles import (
        list_zipcode_profiles as db_list,
    )

    profiles = await db_list()
    return [_serialize(p) for p in profiles]


@router.delete("/{zip_code}")
async def delete_zipcode_profile(zip_code: str):
    """Delete a zipcode profile."""
    from hephae_db.firestore.zipcode_profiles import (
        get_zipcode_profile as db_get,
        delete_zipcode_profile as db_delete,
    )

    existing = await db_get(zip_code)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No profile found for {zip_code}")

    await db_delete(zip_code)
    return {"success": True}


@router.post("/{zip_code}/refresh")
async def refresh_zipcode_profile(zip_code: str):
    """Re-run discovery for an existing zip code (full refresh)."""
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code — must be 5 digits")

    from hephae_agents.research.zipcode_profile_discovery import (
        run_zipcode_profile_discovery,
    )

    logger.info(f"[ZipcodeProfiles] Refreshing profile for {zip_code}")
    try:
        profile = await run_zipcode_profile_discovery(zip_code)
    except Exception as e:
        logger.error(f"[ZipcodeProfiles] Refresh failed for {zip_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")

    if profile.get("error"):
        raise HTTPException(status_code=404, detail=profile["error"])

    return {
        "success": True,
        "zipCode": zip_code,
        "confirmedSources": profile.get("confirmedSources", 0),
        "unavailableSources": profile.get("unavailableSources", 0),
        "profile": _serialize(profile),
    }
