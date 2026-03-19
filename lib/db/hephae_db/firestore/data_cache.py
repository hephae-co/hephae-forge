"""Firestore data_cache collection — shared TTL-based cache for pulse signals.

Stores fetched data from external sources (BLS, Census, FDA, etc.) with
configurable TTL. Eliminates redundant API calls when running pulses for
multiple zip codes in the same county/state.

Document ID pattern: {source}:{scope_key}
  e.g., "census:07110", "fda:NJ", "qcew:34031-2024-Q1"
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "data_cache"

# TTL tiers (days)
TTL_STATIC = 90       # Census, FHFA, IRS, CDC, OSM — annual data
TTL_SHARED = 30       # QCEW, FBI, FDA, EIA, USDA — county/state quarterly
TTL_WEEKLY = 7        # NWS, news, trends, CPI, SBA — weekly refresh
TTL_DAILY = 1         # Intra-day (not used yet, placeholder)


async def get_cached(
    source: str,
    scope_key: str,
) -> dict[str, Any] | None:
    """Retrieve cached data if it exists and hasn't expired.

    Returns the cached data dict, or None if missing/expired.
    """
    db = get_db()
    doc_id = f"{source}:{scope_key}"
    doc_ref = db.collection(CACHE_COLLECTION).document(doc_id)
    doc = await asyncio.to_thread(doc_ref.get)

    if not doc.exists:
        return None

    data = doc.to_dict()
    expires_at = data.get("expiresAt")
    if expires_at:
        # Normalize to naive UTC datetime for comparison
        if hasattr(expires_at, "seconds"):
            exp_dt = datetime.utcfromtimestamp(expires_at.seconds)
        elif isinstance(expires_at, datetime):
            # Strip timezone info to avoid naive vs aware comparison
            exp_dt = expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at
        else:
            exp_dt = datetime.min

        if datetime.utcnow() > exp_dt:
            logger.info(f"[DataCache] Expired: {doc_id} (expired {exp_dt.isoformat()})")
            return None

    logger.info(f"[DataCache] Hit: {doc_id}")
    return data.get("data")


async def set_cached(
    source: str,
    scope_key: str,
    data: dict[str, Any],
    ttl_days: int = TTL_WEEKLY,
) -> None:
    """Store data in the cache with a TTL.

    Args:
        source: Data source name (e.g., "census", "fda", "qcew").
        scope_key: Scope identifier (e.g., zip code, state code, county FIPS).
        data: The data to cache.
        ttl_days: TTL in days.
    """
    db = get_db()
    doc_id = f"{source}:{scope_key}"
    now = datetime.utcnow()

    doc_ref = db.collection(CACHE_COLLECTION).document(doc_id)
    payload = {
        "source": source,
        "scopeKey": scope_key,
        "data": data,
        "fetchedAt": now,
        "ttlDays": ttl_days,
        "expiresAt": now + timedelta(days=ttl_days),
    }
    await asyncio.to_thread(doc_ref.set, payload)
    logger.info(f"[DataCache] Set: {doc_id} (TTL={ttl_days}d)")


async def invalidate(source: str, scope_key: str) -> None:
    """Delete a cache entry."""
    db = get_db()
    doc_id = f"{source}:{scope_key}"
    doc_ref = db.collection(CACHE_COLLECTION).document(doc_id)
    await asyncio.to_thread(doc_ref.delete)
    logger.info(f"[DataCache] Invalidated: {doc_id}")
