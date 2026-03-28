"""Business profile link — save and retrieve shareable business profiles.

Also persists a memory summary to the user's long-term ADK memory
so the chat agent remembers past analysis for this business.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_request, optional_firebase_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/b/save", dependencies=[Depends(verify_request)])
async def save_business_profile(
    request: Request,
    firebase_user: dict | None = Depends(optional_firebase_user),
):
    """Save a business identity under a slug for shareable URL."""
    try:
        body = await request.json()
        slug = body.get("slug")
        identity = body.get("identity")
        snapshot = body.get("snapshot")       # full snapshot (from overview save)
        snapshot_update = body.get("snapshotUpdate")  # partial update (from capability save)

        if not slug or not identity:
            return JSONResponse({"error": "slug and identity required"}, status_code=400)

        from hephae_common.firebase import get_db
        db = get_db()
        doc_ref = db.collection("business_profiles").document(slug)

        if snapshot_update:
            # Merge only the new capability key into the existing snapshot
            update_payload = {f"snapshot.{k}": v for k, v in snapshot_update.items()}
            update_payload["updatedAt"] = datetime.utcnow().isoformat()
            # Ensure doc exists first
            doc_ref.set({
                "slug": slug,
                "identity": identity,
                "name": identity.get("name", ""),
                "address": identity.get("address", ""),
            }, merge=True)
            doc_ref.update(update_payload)
        else:
            doc_ref.set({
                "slug": slug,
                "identity": identity,
                "savedAt": datetime.utcnow().isoformat(),
                "name": identity.get("name", ""),
                "address": identity.get("address", ""),
                **({"snapshot": snapshot} if snapshot else {}),
            }, merge=True)

        logger.info(f"[BusinessProfile] Saved: {slug}")

        # Persist a memory summary for authenticated users
        uid = firebase_user.get("uid") if firebase_user else None
        if uid and (snapshot or snapshot_update):
            asyncio.create_task(_save_business_memory(uid, slug, identity, snapshot, snapshot_update))

        return JSONResponse({"slug": slug, "url": f"/b/{slug}"})

    except Exception as e:
        logger.error(f"[BusinessProfile] Save failed: {e}")
        return JSONResponse({"error": "save failed"}, status_code=500)


async def _save_business_memory(
    uid: str,
    slug: str,
    identity: dict,
    snapshot: dict | None,
    snapshot_update: dict | None,
) -> None:
    """Save a compact memory entry summarizing what we know about this business.

    This feeds into the chat agent's long-term memory so it can reference
    past analysis when the user returns via /b/{slug}.
    """
    try:
        from hephae_db.memory.firestore_memory_service import FirestoreMemoryService
        from google.adk.memory.memory_entry import MemoryEntry
        from google.genai.types import Content, Part

        name = identity.get("name", "unknown")
        address = identity.get("address", "")

        # Build a compact summary of what's been discovered/analyzed
        parts = [f"Business: {name} at {address} (slug: {slug})"]

        data = snapshot or {}
        if snapshot_update:
            data = {**data, **snapshot_update}

        ov = data.get("overview", {})
        if ov:
            bs = ov.get("businessSnapshot", {})
            if bs.get("rating"):
                parts.append(f"Rating: {bs['rating']}/5 ({bs.get('reviewCount', '?')} reviews)")
            mp = ov.get("marketPosition", {})
            if mp.get("competitorCount"):
                parts.append(f"Market: {mp['competitorCount']} competitors, {mp.get('saturationLevel', '?')} saturation")
            opps = ov.get("keyOpportunities", [])
            if opps:
                parts.append("Opportunities: " + "; ".join(o.get("title", "") for o in opps[:3]))
            dash = ov.get("dashboard", {})
            if dash.get("topInsights"):
                parts.append("Insights: " + "; ".join(i.get("title", "") for i in dash["topInsights"][:3]))

        if data.get("margin", {}).get("data"):
            m = data["margin"]["data"]
            parts.append(f"Margin analysis: score {m.get('overall_score', '?')}/100")
        if data.get("seo", {}).get("data"):
            s = data["seo"]["data"]
            parts.append(f"SEO audit: score {s.get('overallScore', '?')}/100")
        if data.get("traffic", {}).get("data"):
            parts.append("Traffic forecast: completed")
        if data.get("competitive", {}).get("data"):
            parts.append("Competitive analysis: completed")
        if data.get("marketing", {}).get("data"):
            parts.append("Social media audit: completed")

        if len(parts) <= 1:
            return  # Nothing meaningful to save

        summary = "\n".join(parts)

        ms = FirestoreMemoryService()
        await ms.add_memory(
            app_name="hephae-chat",
            user_id=uid,
            memories=[MemoryEntry(
                content=Content(role="model", parts=[Part.from_text(text=summary)]),
            )],
        )
        logger.info(f"[BusinessProfile] Memory saved for {uid}/{slug}: {len(parts)} facts")

    except Exception as e:
        logger.warning(f"[BusinessProfile] Memory save failed: {e}")


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
