"""Firestore cache for food price data (BLS CPI + USDA NASS)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from backend.lib.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "food_price_cache"
CACHE_TTL = timedelta(hours=24)


def _make_doc_id(source: str, industry: str, state: str = "") -> str:
    """Generate a cache document ID."""
    slug = industry.lower().strip().replace(" ", "_")
    if source == "usda" and state:
        return f"usda_{slug}_{state.lower().strip()}"
    return f"{source}_{slug}"


async def get_cached_food_prices(
    source: str, industry: str, state: str = ""
) -> dict[str, Any] | None:
    """Return cached data dict if it exists and is fresh (< 24h old).

    Returns None on miss or stale cache.
    """
    try:
        db = get_db()
        doc_id = _make_doc_id(source, industry, state)
        snapshot = await asyncio.to_thread(
            db.collection(COLLECTION).document(doc_id).get
        )
        if not snapshot.exists:
            return None

        doc = snapshot.to_dict()
        fetched_at = doc.get("fetchedAt")
        if fetched_at is None:
            return None

        # Firestore timestamps have a .seconds attribute
        if hasattr(fetched_at, "seconds"):
            fetched_dt = datetime.utcfromtimestamp(
                fetched_at.seconds + fetched_at.nanoseconds / 1e9
            )
        elif isinstance(fetched_at, datetime):
            fetched_dt = fetched_at
        else:
            return None

        if datetime.utcnow() - fetched_dt > CACHE_TTL:
            logger.debug(f"[FoodPriceCache] Stale cache for {doc_id}")
            return None

        logger.info(f"[FoodPriceCache] Cache hit for {doc_id}")
        return doc.get("data")
    except Exception as e:
        logger.warning(f"[FoodPriceCache] Read error: {e}")
        return None


async def save_food_prices_cache(
    source: str, industry: str, state: str, data: dict[str, Any]
) -> None:
    """Upsert cached food price data with current timestamp."""
    try:
        db = get_db()
        doc_id = _make_doc_id(source, industry, state)

        doc_data = {
            "source": source,
            "industry": industry,
            "state": state,
            "data": data,
            "fetchedAt": datetime.utcnow(),
        }

        await asyncio.to_thread(
            db.collection(COLLECTION).document(doc_id).set, doc_data
        )
        logger.info(f"[FoodPriceCache] Cached {doc_id}")
    except Exception as e:
        logger.warning(f"[FoodPriceCache] Write error: {e}")
