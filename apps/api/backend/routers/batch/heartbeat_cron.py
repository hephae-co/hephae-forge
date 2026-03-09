"""Heartbeat cron — weekly capability re-run cycle."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["heartbeat-cron"])


@router.get("/api/cron/heartbeat-cycle")
async def heartbeat_cycle(authorization: str | None = Header(None)):
    """Run all due heartbeat cycles. Called by Cloud Scheduler weekly."""
    if settings.CRON_SECRET and authorization != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.heartbeats import get_due_heartbeats
    from backend.workflows.heartbeat_runner import run_heartbeat_cycle

    now = datetime.utcnow()
    due = await get_due_heartbeats(now)
    logger.info(f"[Heartbeat Cron] Found {len(due)} due heartbeats")

    results = []
    for hb in due:
        try:
            result = await run_heartbeat_cycle(hb)
            results.append({"id": hb["id"], **result})
        except Exception as e:
            logger.error(f"[Heartbeat Cron] Failed for {hb['id']}: {e}")
            results.append({"id": hb["id"], "status": "error", "error": str(e)})

    processed = len(results)
    emailed = sum(1 for r in results if r.get("status") == "completed")
    skipped = sum(1 for r in results if r.get("status") == "skipped")

    return {"processed": processed, "emailed": emailed, "skipped": skipped, "details": results}
