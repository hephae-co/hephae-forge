"""
readBusiness — read path for business documents.

Provides Firestore reads so capability routes can access previously
discovered data (menu URLs, brand colors, logo, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.lib.report_storage import generate_slug

logger = logging.getLogger(__name__)


def read_business(slug: str) -> Optional[dict[str, Any]]:
    """Read a business document from Firestore by slug.

    Returns the document dict, or None if it doesn't exist.
    """
    try:
        from backend.lib.firebase import db

        doc = db.document(f"businesses/{slug}").get()
        return doc.to_dict() if doc.exists else None
    except Exception as err:
        logger.warning(f"[DB] Firestore read failed for businesses/{slug}: {err}")
        return None


def enrich_identity(identity: dict[str, Any]) -> dict[str, Any]:
    """Merge a request identity with stored Firestore data.

    Stored fields fill gaps — the request's own values always win.
    This ensures that capabilities have full context (menu URLs, brand
    colors, logo, favicon, etc.) even if the frontend omitted them.
    """
    name = identity.get("name")
    if not name:
        return identity

    slug = generate_slug(name)
    stored = read_business(slug)
    if not stored:
        return identity

    # Stored values as base, then overlay request values (non-None only)
    merged = {**stored}
    for k, v in identity.items():
        if v is not None:
            merged[k] = v

    # Never leak internal Firestore metadata to the API response
    for key in ("createdAt", "updatedAt", "latestOutputs", "crm", "identity"):
        merged.pop(key, None)

    return merged
