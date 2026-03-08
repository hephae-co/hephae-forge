"""
Business document read/write — merged from web and admin.

Web: read_business, enrich_identity
Admin: get_business, get_businesses_by_zip, get_businesses_for_workflow
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)


def generate_slug(name: str) -> str:
    """Convert a business name to a URL-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = slug.strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug


def _read_business_sync(slug: str) -> Optional[dict[str, Any]]:
    try:
        db = get_db()
        doc = db.document(f"businesses/{slug}").get()
        return doc.to_dict() if doc.exists else None
    except Exception as err:
        logger.warning(f"[DB] Firestore read failed for businesses/{slug}: {err}")
        return None


def read_business(slug: str) -> Optional[dict[str, Any]]:
    """Read a business document from Firestore by slug (sync).

    Returns the document dict, or None if it doesn't exist.
    """
    return _read_business_sync(slug)


async def get_business(slug: str) -> Optional[dict[str, Any]]:
    """Read a business document from Firestore by slug (async)."""
    return await asyncio.to_thread(_read_business_sync, slug)


def enrich_identity(identity: dict[str, Any]) -> dict[str, Any]:
    """Merge a request identity with stored Firestore data.

    Stored fields fill gaps — the request's own values always win.
    """
    name = identity.get("name")
    if not name:
        return identity

    slug = generate_slug(name)
    stored = read_business(slug)
    if not stored:
        return identity

    merged = {**stored}
    for k, v in identity.items():
        if v is not None:
            merged[k] = v

    for key in ("createdAt", "updatedAt", "latestOutputs", "crm", "identity"):
        merged.pop(key, None)

    return merged


def _save_business_sync(slug: str, data: dict[str, Any]) -> None:
    try:
        db = get_db()
        db.document(f"businesses/{slug}").set(data, merge=True)
    except Exception as err:
        logger.warning(f"[DB] Firestore write failed for businesses/{slug}: {err}")


async def save_business(slug: str, data: dict[str, Any]) -> None:
    """Write/update a business document in Firestore."""
    await asyncio.to_thread(_save_business_sync, slug, data)


def _delete_business_sync(slug: str) -> None:
    try:
        db = get_db()
        db.document(f"businesses/{slug}").delete()
    except Exception as err:
        logger.warning(f"[DB] Firestore delete failed for businesses/{slug}: {err}")


async def delete_business(slug: str) -> None:
    """Delete a business document from Firestore."""
    await asyncio.to_thread(_delete_business_sync, slug)


def _get_businesses_by_zip_sync(zip_code: str, limit: int = 100) -> list[dict[str, Any]]:
    try:
        db = get_db()
        query = db.collection("businesses").where("zipCode", "==", zip_code)
        if limit:
            query = query.limit(limit)
        docs = query.get()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]
    except Exception as err:
        logger.warning(f"[DB] Failed to read businesses for zip {zip_code}: {err}")
        return []


async def get_businesses_by_zip(zip_code: str, limit: int = 100) -> list[dict[str, Any]]:
    """Read all businesses in a zip code (async)."""
    return await asyncio.to_thread(_get_businesses_by_zip_sync, zip_code, limit)


# Alias for code that uses get_businesses_in_zipcode
get_businesses_in_zipcode = get_businesses_by_zip


def _get_businesses_paginated_sync(
    zip_code: str,
    page: int = 1,
    page_size: int = 25,
    category: Optional[str] = None,
    status: Optional[str] = None,
    has_email: Optional[bool] = None,
    name: Optional[str] = None,
) -> dict[str, Any]:
    try:
        db = get_db()
        query = db.collection("businesses").where("zipCode", "==", zip_code)
        if category:
            query = query.where("category", "==", category)
        if status:
            query = query.where("discoveryStatus", "==", status)

        docs = query.get()
        businesses = [doc.to_dict() | {"id": doc.id} for doc in docs]

        # Post-filter for has_email (not indexable in Firestore)
        if has_email is not None:
            businesses = [
                b for b in businesses
                if bool(b.get("email") or (b.get("identity") or {}).get("email")) == has_email
            ]

        # Post-filter for name (substring match, case-insensitive)
        if name:
            name_lower = name.lower()
            businesses = [b for b in businesses if name_lower in (b.get("name") or "").lower()]

        # Sort by name
        businesses.sort(key=lambda b: (b.get("name") or "").lower())

        total = len(businesses)
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        return {
            "businesses": businesses[start:start + page_size],
            "total": total,
            "page": page,
            "pages": pages,
            "pageSize": page_size,
        }
    except Exception as err:
        logger.warning(f"[DB] Failed to paginate businesses for zip {zip_code}: {err}")
        return {"businesses": [], "total": 0, "page": 1, "pages": 1, "pageSize": page_size}


async def get_businesses_paginated(
    zip_code: str,
    page: int = 1,
    page_size: int = 25,
    category: Optional[str] = None,
    status: Optional[str] = None,
    has_email: Optional[bool] = None,
    name: Optional[str] = None,
) -> dict[str, Any]:
    """Read businesses in a zip code with pagination and filters (async)."""
    return await asyncio.to_thread(
        _get_businesses_paginated_sync, zip_code, page, page_size, category, status, has_email, name
    )


def _get_businesses_for_workflow_sync(workflow_id: str) -> list[dict[str, Any]]:
    try:
        db = get_db()
        docs = db.collection("businesses").where("workflowId", "==", workflow_id).get()
        return [doc.to_dict() | {"id": doc.id} for doc in docs]
    except Exception as err:
        logger.warning(f"[DB] Failed to read businesses for workflow {workflow_id}: {err}")
        return []


async def get_businesses_for_workflow(workflow_id: str) -> list[dict[str, Any]]:
    """Read businesses associated with a workflow."""
    return await asyncio.to_thread(_get_businesses_for_workflow_sync, workflow_id)
