"""Dashboard stats aggregation across Firestore collections."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)


async def get_dashboard_stats() -> dict[str, Any]:
    """Query 5 collections in parallel and return aggregated dashboard stats."""
    db = get_db()

    async def _zipcode_stats() -> dict[str, Any]:
        docs = await asyncio.to_thread(
            db.collection("zipcode_research")
            .select(["zipCode", "createdAt"])
            .get
        )
        zip_codes: set[str] = set()
        last_run_at: datetime | None = None
        for doc in docs:
            data = doc.to_dict()
            zc = data.get("zipCode", "")
            if zc:
                zip_codes.add(zc)
            created = data.get("createdAt")
            if created:
                if hasattr(created, "seconds"):
                    created = datetime.utcfromtimestamp(created.seconds + created.nanoseconds / 1e9)
                if last_run_at is None or created > last_run_at:
                    last_run_at = created
        return {
            "totalRuns": len(docs),
            "uniqueZipCodes": len(zip_codes),
            "lastRunAt": last_run_at.isoformat() if last_run_at else None,
        }

    async def _area_research_count() -> int:
        docs = await asyncio.to_thread(
            db.collection("area_research").select([]).get
        )
        return len(docs)

    async def _combined_context_count() -> int:
        docs = await asyncio.to_thread(
            db.collection("combined_contexts").select([]).get
        )
        return len(docs)

    async def _workflow_stats() -> dict[str, Any]:
        docs = await asyncio.to_thread(
            db.collection("workflows")
            .select(["phase", "progress"])
            .get
        )
        total = len(docs)
        completed = 0
        total_discovered = 0
        total_outreach = 0
        for doc in docs:
            data = doc.to_dict()
            if data.get("phase") == "completed":
                completed += 1
            progress = data.get("progress", {})
            total_discovered += progress.get("totalBusinesses", 0)
            total_outreach += progress.get("outreachComplete", 0)
        return {
            "totalWorkflows": total,
            "completedWorkflows": completed,
            "totalBusinessesDiscovered": total_discovered,
            "totalOutreachComplete": total_outreach,
        }

    async def _business_stats() -> dict[str, Any]:
        docs = await asyncio.to_thread(
            db.collection("businesses")
            .select(["discoveryStatus", "zipCode"])
            .get
        )
        total = len(docs)
        by_status: Counter[str] = Counter()
        zip_codes: set[str] = set()
        for doc in docs:
            data = doc.to_dict()
            status = data.get("discoveryStatus", "scanned")
            by_status[status] += 1
            zc = data.get("zipCode", "")
            if zc:
                zip_codes.add(zc)
        return {
            "totalBusinesses": total,
            "discovered": by_status.get("discovered", 0) + by_status.get("analyzed", 0),
            "analyzed": by_status.get("analyzed", 0),
            "uniqueZipCodes": len(zip_codes),
        }

    async def _content_stats() -> dict[str, Any]:
        docs = await asyncio.to_thread(
            db.collection("content_posts")
            .select(["status", "platform"])
            .get
        )
        total = len(docs)
        published = 0
        by_platform: Counter[str] = Counter()
        for doc in docs:
            data = doc.to_dict()
            if data.get("status") == "published":
                published += 1
            platform = data.get("platform", "unknown")
            by_platform[platform] += 1
        return {
            "totalPosts": total,
            "publishedPosts": published,
            "byPlatform": dict(by_platform),
        }

    (
        zipcode,
        area_count,
        combined_count,
        workflows,
        content,
        businesses,
    ) = await asyncio.gather(
        _zipcode_stats(),
        _area_research_count(),
        _combined_context_count(),
        _workflow_stats(),
        _content_stats(),
        _business_stats(),
    )

    return {
        "research": {
            **zipcode,
            "areaResearchCount": area_count,
            "combinedContextCount": combined_count,
        },
        "workflows": workflows,
        "content": content,
        "businesses": businesses,
    }
