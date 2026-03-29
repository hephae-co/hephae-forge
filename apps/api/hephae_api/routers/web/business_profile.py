"""Business profile — versioned, publishable business case studies.

Data model:
  business_profiles/{slug}
    ├── identity, name, address, createdBy (uid)
    ├── publishedVersionId: "v3" | null
    ├── latestVersionId: "v5"
    ├── snapshot: { current working snapshot }
    └── versions/{versionId}: { snapshot, createdAt, createdBy, label }

Three access levels:
  - Public (no auth): read published version only (SSR-friendly)
  - Owner (auth, createdBy match): read/write, create versions
  - Superadmin (auth, admin allowlist): read/write, publish/unpublish any version
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_request, optional_firebase_user, verify_firebase_token

logger = logging.getLogger(__name__)
router = APIRouter()

COLLECTION = "business_profiles"


def _is_admin(uid: str) -> bool:
    """Check if user is a superadmin."""
    import os
    allowlist = os.getenv("ADMIN_EMAIL_ALLOWLIST", "")
    # We check by uid here but the allowlist is emails — need to check via firebase_user email
    return False  # Caller should pass the full user dict


def _is_admin_user(firebase_user: dict | None) -> bool:
    """Check if firebase user is in admin allowlist."""
    if not firebase_user:
        return False
    import os
    email = firebase_user.get("email", "")
    allowlist = [e.strip().lower() for e in os.getenv("ADMIN_EMAIL_ALLOWLIST", "").split(",") if e.strip()]
    return email.lower() in allowlist


# ---------------------------------------------------------------------------
# POST /api/b/save — save snapshot + auto-create version
# ---------------------------------------------------------------------------

@router.post("/b/save", dependencies=[Depends(verify_request)])
async def save_business_profile(
    request: Request,
    firebase_user: dict | None = Depends(optional_firebase_user),
):
    """Save a business profile. Auto-creates a new version on each save."""
    try:
        body = await request.json()
        slug = body.get("slug")
        identity = body.get("identity")
        snapshot = body.get("snapshot")
        snapshot_update = body.get("snapshotUpdate")

        if not slug or not identity:
            return JSONResponse({"error": "slug and identity required"}, status_code=400)

        from hephae_common.firebase import get_db
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(slug)
        uid = firebase_user.get("uid") if firebase_user else None
        now = datetime.now(timezone.utc).isoformat()

        # Read existing doc to get current snapshot for merging
        existing = doc_ref.get()
        existing_data = existing.to_dict() if existing.exists else {}
        current_snapshot = existing_data.get("snapshot", {})

        if snapshot_update:
            # Merge update into current snapshot
            merged = {**current_snapshot, **{k: v for k, v in snapshot_update.items()}}
            doc_ref.set({
                "slug": slug,
                "identity": identity,
                "name": identity.get("name", ""),
                "address": identity.get("address", ""),
                "snapshot": merged,
                "updatedAt": now,
                **({"createdBy": uid} if uid and not existing_data.get("createdBy") else {}),
            }, merge=True)
            final_snapshot = merged
        else:
            doc_ref.set({
                "slug": slug,
                "identity": identity,
                "savedAt": now,
                "updatedAt": now,
                "name": identity.get("name", ""),
                "address": identity.get("address", ""),
                **({"snapshot": snapshot} if snapshot else {}),
                **({"createdBy": uid} if uid and not existing_data.get("createdBy") else {}),
            }, merge=True)
            final_snapshot = snapshot or current_snapshot

        # Auto-create a version on each save (if we have a snapshot)
        version_id = None
        if final_snapshot and uid:
            version_id = f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            doc_ref.collection("versions").document(version_id).set({
                "snapshot": final_snapshot,
                "createdAt": now,
                "createdBy": uid,
                "label": f"Auto-save",
            })
            doc_ref.update({"latestVersionId": version_id})

        logger.info(f"[BusinessProfile] Saved: {slug} (version: {version_id})")

        # Persist memory for authenticated users
        if uid and final_snapshot:
            asyncio.create_task(_save_business_memory(uid, slug, identity, final_snapshot))

        return JSONResponse({"slug": slug, "url": f"/b/{slug}", "versionId": version_id})

    except Exception as e:
        logger.error(f"[BusinessProfile] Save failed: {e}")
        return JSONResponse({"error": "save failed"}, status_code=500)


# ---------------------------------------------------------------------------
# GET /api/b/{slug} — fetch profile (with auth: full data; without: published only)
# ---------------------------------------------------------------------------

@router.get("/b/{slug}", dependencies=[Depends(verify_request)])
async def get_business_profile(
    slug: str,
    firebase_user: dict | None = Depends(optional_firebase_user),
):
    """Fetch a business profile.

    Authenticated owner/admin: returns full profile with all versions.
    Unauthenticated: returns published version only (for public pages).
    """
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc = db.collection(COLLECTION).document(slug).get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()
        uid = firebase_user.get("uid") if firebase_user else None
        is_owner = uid and data.get("createdBy") == uid
        is_admin = _is_admin_user(firebase_user)

        if is_owner or is_admin:
            # Full access — include version list
            versions_ref = db.collection(COLLECTION).document(slug).collection("versions")
            versions = versions_ref.order_by("createdAt", direction="DESCENDING").limit(20).get()
            data["versions"] = [
                {"id": v.id, **{k: v.to_dict()[k] for k in ("createdAt", "createdBy", "label") if k in v.to_dict()}}
                for v in versions
            ]
            data["isOwner"] = bool(is_owner)
            data["isAdmin"] = bool(is_admin)
            return JSONResponse(data)

        # Public access — only return published version
        published_id = data.get("publishedVersionId")
        if not published_id:
            return JSONResponse({"error": "not found"}, status_code=404)

        version_doc = db.collection(COLLECTION).document(slug).collection("versions").document(published_id).get()
        if not version_doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        version_data = version_doc.to_dict()
        return JSONResponse({
            "slug": slug,
            "identity": data.get("identity"),
            "name": data.get("name"),
            "address": data.get("address"),
            "snapshot": version_data.get("snapshot"),
            "publishedAt": version_data.get("createdAt"),
            "published": True,
        })

    except Exception as e:
        logger.error(f"[BusinessProfile] Fetch failed for {slug}: {e}")
        return JSONResponse({"error": "fetch failed"}, status_code=500)


# ---------------------------------------------------------------------------
# GET /api/b/{slug}/public — always returns published version (no auth needed)
# ---------------------------------------------------------------------------

@router.get("/b/{slug}/public")
async def get_public_profile(slug: str):
    """Fetch a business profile for public display. No auth required.

    Resolution order:
    1. Explicitly published version (publishedVersionId)
    2. Latest auto-saved version (latestVersionId)
    3. Raw snapshot on the document (no versioning)
    """
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc = db.collection(COLLECTION).document(slug).get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()

        # Try published version first, then latest version
        version_id = data.get("publishedVersionId") or data.get("latestVersionId")
        snapshot = None
        published_at = None

        if version_id:
            version_doc = db.collection(COLLECTION).document(slug).collection("versions").document(version_id).get()
            if version_doc.exists:
                version_data = version_doc.to_dict()
                snapshot = version_data.get("snapshot")
                published_at = version_data.get("createdAt")

        # Fallback: use the raw snapshot on the document
        if not snapshot:
            snapshot = data.get("snapshot")
            published_at = data.get("updatedAt") or data.get("savedAt")

        if not snapshot and not data.get("identity"):
            return JSONResponse({"error": "no profile data"}, status_code=404)

        return JSONResponse({
            "slug": slug,
            "identity": data.get("identity"),
            "name": data.get("name"),
            "address": data.get("address"),
            "snapshot": snapshot,
            "publishedAt": published_at,
            "publishedVersionId": data.get("publishedVersionId"),
        })

    except Exception as e:
        logger.error(f"[BusinessProfile] Public fetch failed for {slug}: {e}")
        return JSONResponse({"error": "fetch failed"}, status_code=500)


# ---------------------------------------------------------------------------
# POST /api/b/{slug}/publish — publish a specific version (owner or admin)
# ---------------------------------------------------------------------------

@router.post("/b/{slug}/publish")
async def publish_version(slug: str, request: Request, firebase_user: dict = Depends(verify_firebase_token)):
    """Publish a specific version as the public page."""
    try:
        body = await request.json()
        version_id = body.get("versionId")
        if not version_id:
            return JSONResponse({"error": "versionId required"}, status_code=400)

        from hephae_common.firebase import get_db
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(slug)
        doc = doc_ref.get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()
        uid = firebase_user.get("uid")
        is_owner = uid == data.get("createdBy")
        is_admin = _is_admin_user(firebase_user)

        if not is_owner and not is_admin:
            return JSONResponse({"error": "Not authorized"}, status_code=403)

        # Verify version exists
        version_doc = doc_ref.collection("versions").document(version_id).get()
        if not version_doc.exists:
            return JSONResponse({"error": f"Version {version_id} not found"}, status_code=404)

        doc_ref.update({
            "publishedVersionId": version_id,
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "publishedBy": uid,
        })

        logger.info(f"[BusinessProfile] Published {slug} version {version_id} by {uid}")
        return JSONResponse({"slug": slug, "publishedVersionId": version_id, "url": f"/b/{slug}"})

    except Exception as e:
        logger.error(f"[BusinessProfile] Publish failed: {e}")
        return JSONResponse({"error": "publish failed"}, status_code=500)


# ---------------------------------------------------------------------------
# POST /api/b/{slug}/unpublish — remove from public (owner or admin)
# ---------------------------------------------------------------------------

@router.post("/b/{slug}/unpublish")
async def unpublish_profile(slug: str, firebase_user: dict = Depends(verify_firebase_token)):
    """Remove the public version. Profile becomes private."""
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc_ref = db.collection(COLLECTION).document(slug)
        doc = doc_ref.get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()
        uid = firebase_user.get("uid")
        if uid != data.get("createdBy") and not _is_admin_user(firebase_user):
            return JSONResponse({"error": "Not authorized"}, status_code=403)

        doc_ref.update({"publishedVersionId": None, "publishedAt": None, "publishedBy": None})
        logger.info(f"[BusinessProfile] Unpublished {slug} by {uid}")
        return JSONResponse({"slug": slug, "published": False})

    except Exception as e:
        logger.error(f"[BusinessProfile] Unpublish failed: {e}")
        return JSONResponse({"error": "unpublish failed"}, status_code=500)


# ---------------------------------------------------------------------------
# GET /api/b/{slug}/versions — list all versions (owner or admin)
# ---------------------------------------------------------------------------

@router.get("/b/{slug}/versions")
async def list_versions(slug: str, firebase_user: dict = Depends(verify_firebase_token)):
    """List all versions for a business profile."""
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc = db.collection(COLLECTION).document(slug).get()

        if not doc.exists:
            return JSONResponse({"error": "not found"}, status_code=404)

        data = doc.to_dict()
        uid = firebase_user.get("uid")
        if uid != data.get("createdBy") and not _is_admin_user(firebase_user):
            return JSONResponse({"error": "Not authorized"}, status_code=403)

        versions = db.collection(COLLECTION).document(slug).collection("versions") \
            .order_by("createdAt", direction="DESCENDING").limit(50).get()

        return JSONResponse({
            "slug": slug,
            "publishedVersionId": data.get("publishedVersionId"),
            "versions": [
                {"id": v.id, **v.to_dict()}
                for v in versions
            ],
        })

    except Exception as e:
        logger.error(f"[BusinessProfile] List versions failed: {e}")
        return JSONResponse({"error": "list failed"}, status_code=500)


# ---------------------------------------------------------------------------
# Memory persistence (unchanged)
# ---------------------------------------------------------------------------

async def _save_business_memory(
    uid: str, slug: str, identity: dict, snapshot: dict,
) -> None:
    """Save a compact memory entry for the chat agent."""
    try:
        from hephae_db.memory.firestore_memory_service import FirestoreMemoryService
        from google.adk.memory.memory_entry import MemoryEntry
        from google.genai.types import Content, Part

        name = identity.get("name", "unknown")
        address = identity.get("address", "")
        parts = [f"Business: {name} at {address} (slug: {slug})"]

        ov = snapshot.get("overview", {})
        if ov:
            bs = ov.get("businessSnapshot", {})
            if bs.get("rating"):
                parts.append(f"Rating: {bs['rating']}/5 ({bs.get('reviewCount', '?')} reviews)")
            mp = ov.get("marketPosition", {})
            if mp.get("competitorCount"):
                parts.append(f"Market: {mp['competitorCount']} competitors")
            dash = ov.get("dashboard", {})
            if dash.get("topInsights"):
                parts.append("Insights: " + "; ".join(i.get("title", "") for i in dash["topInsights"][:3]))

        for cap, label in [("margin", "Margin"), ("seo", "SEO"), ("traffic", "Traffic"), ("competitive", "Competitive"), ("marketing", "Social")]:
            if snapshot.get(cap, {}).get("data"):
                score = snapshot[cap]["data"].get("overall_score") or snapshot[cap]["data"].get("overallScore")
                parts.append(f"{label}: {'score ' + str(score) + '/100' if score else 'completed'}")

        if len(parts) <= 1:
            return

        ms = FirestoreMemoryService()
        await ms.add_memory(
            app_name="hephae-chat", user_id=uid,
            memories=[MemoryEntry(content=Content(role="model", parts=[Part.from_text(text="\n".join(parts))]))],
        )
        logger.info(f"[BusinessProfile] Memory saved for {uid}/{slug}")
    except Exception as e:
        logger.warning(f"[BusinessProfile] Memory save failed: {e}")
