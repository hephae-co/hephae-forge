"""
Firestore readers for admin-produced research data.

Collections read:
  - zipcode_research  — demographics, events, weather, trending per zip code
  - area_research     — market opportunity, competitive landscape, industry intel
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def get_zipcode_report(zip_code: str) -> Optional[dict[str, Any]]:
    """Read the latest completed zipcode_research for a zip code."""
    if not zip_code:
        return None
    try:
        from hephae_common.firebase import get_db

        db = get_db()
        query = (
            db.collection("zipcode_research")
            .where("zipCode", "==", zip_code)
            .order_by("createdAt", direction="DESCENDING")
            .limit(1)
        )
        docs = await asyncio.to_thread(query.get)
        if docs:
            data = docs[0].to_dict()
            return data.get("report") if data else None
        return None
    except Exception as e:
        logger.warning(f"[AdminData] Failed to read zipcode_research for {zip_code}: {e}")
        return None


async def get_area_research_for_zip(zip_code: str) -> Optional[dict[str, Any]]:
    """Read completed area_research that includes a specific zip code."""
    if not zip_code:
        return None
    try:
        from hephae_common.firebase import get_db

        db = get_db()
        query = (
            db.collection("area_research")
            .where("zipCodes", "array_contains", zip_code)
            .where("phase", "==", "completed")
            .order_by("createdAt", direction="DESCENDING")
            .limit(1)
        )
        docs = await asyncio.to_thread(query.get)
        if docs:
            data = docs[0].to_dict()
            return data.get("summary") if data else None
        return None
    except Exception as e:
        logger.warning(f"[AdminData] Failed to read area_research for {zip_code}: {e}")
        return None
