"""POST /api/auth/me — Create or return user doc on first login."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_firebase_token
from hephae_db.firestore.users import get_or_create_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/auth/me")
async def auth_me(user: dict = Depends(verify_firebase_token)):
    """Called after Google sign-in to sync user doc in Firestore.

    Creates the user doc on first login, updates lastLoginAt on subsequent logins.
    Returns the user document.
    """
    try:
        user_doc = await get_or_create_user(
            uid=user["uid"],
            email=user.get("email"),
            display_name=user.get("name"),
            photo_url=user.get("picture"),
        )

        return JSONResponse({
            "uid": user_doc["uid"],
            "email": user_doc.get("email"),
            "displayName": user_doc.get("displayName"),
            "photoURL": user_doc.get("photoURL"),
            "businesses": user_doc.get("businesses", []),
        })
    except Exception as e:
        logger.error(f"[API/Auth] Failed to sync user: {e}", exc_info=True)
        return JSONResponse({"error": "Failed to sync user"}, status_code=500)
