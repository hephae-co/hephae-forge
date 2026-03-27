"""Business profile link — save and retrieve shareable business profiles."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/b/save", dependencies=[Depends(verify_request)])
async def save_business_profile(request: Request):
    """Save a business identity under a slug for shareable URL."""
    try:
        body = await request.json()
        slug = body.get("slug")
        identity = body.get("identity")

        if not slug or not identity:
            return JSONResponse({"error": "slug and identity required"}, status_code=400)

        from hephae_common.firebase import get_db
        db = get_db()
        doc_ref = db.collection("business_profiles").document(slug)
        doc_ref.set({
            "slug": slug,
            "identity": identity,
            "savedAt": datetime.utcnow().isoformat(),
            "name": identity.get("name", ""),
            "address": identity.get("address", ""),
        }, merge=True)

        logger.info(f"[BusinessProfile] Saved: {slug}")
        return JSONResponse({"slug": slug, "url": f"/b/{slug}"})

    except Exception as e:
        logger.error(f"[BusinessProfile] Save failed: {e}")
        return JSONResponse({"error": "save failed"}, status_code=500)


@router.get("/b/{slug}", dependencies=[Depends(verify_request)])
async def get_business_profile(slug: str):
    """Fetch a saved business profile by slug."""
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc = db.collection("business_profiles").document(slug).get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()
        return JSONResponse(data)

    except Exception as e:
        logger.error(f"[BusinessProfile] Fetch failed for {slug}: {e}")
        return JSONResponse({"error": "fetch failed"}, status_code=500)
