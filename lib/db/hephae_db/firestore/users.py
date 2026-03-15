"""Firestore user data access — manages the users/{uid} collection."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud.firestore_v1 import FieldFilter

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)


async def get_or_create_user(
    uid: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> dict:
    """Get existing user doc or create one on first login.

    Returns the user document as a dict.
    """
    db = get_db()
    doc_ref = db.collection("users").document(uid)
    doc = doc_ref.get()

    now = datetime.now(timezone.utc)

    if doc.exists:
        # Update lastLoginAt on every login
        doc_ref.update({"lastLoginAt": now})
        data = doc.to_dict()
        data["uid"] = uid
        return data

    # First login — create user doc
    user_data = {
        "email": email,
        "displayName": display_name,
        "photoURL": photo_url,
        "createdAt": now,
        "lastLoginAt": now,
        "businesses": [],
    }
    doc_ref.set(user_data)
    user_data["uid"] = uid
    logger.info(f"Created new user: {uid} ({email})")
    return user_data


def get_user(uid: str) -> Optional[dict]:
    """Get a user document by uid. Returns None if not found."""
    db = get_db()
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["uid"] = uid
    return data


def add_business_to_user(uid: str, business_slug: str) -> None:
    """Add a business slug to the user's businesses list (idempotent)."""
    from google.cloud.firestore_v1 import ArrayUnion

    db = get_db()
    db.collection("users").document(uid).update({
        "businesses": ArrayUnion([business_slug]),
    })


def get_user_businesses(uid: str) -> list[str]:
    """Get the list of business slugs associated with a user."""
    user = get_user(uid)
    if not user:
        return []
    return user.get("businesses", [])
