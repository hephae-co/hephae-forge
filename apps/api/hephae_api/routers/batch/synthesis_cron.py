"""Synthesis cron — trigger digest generation for all active industries + zipcodes.

Schedule: Saturday 12:00 PM ET (after all zip pulses complete).

Endpoints:
  GET  /api/cron/synthesis        — Cloud Scheduler trigger (enqueues tasks)
  POST /api/synthesis/execute      — Cloud Tasks callback (runs single digest)
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _current_week_of() -> str:
    """ISO week string for the current week."""
    now = datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


@router.get("/api/cron/synthesis")
async def synthesis_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Trigger synthesis for all active industries + zipcodes.

    Called by Cloud Scheduler every Saturday 12:00 PM ET.
    Enqueues Cloud Tasks for each industry and zip digest.
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    week_of = _current_week_of()
    logger.info(f"[Synthesis Cron] Starting synthesis cycle for {week_of}")

    triggered_industry = 0
    triggered_zip = 0

    try:
        from hephae_api.lib.tasks import enqueue_agent_task

        # Phase 1: Industry digests
        from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes
        active_zips = await _list_active_zips()

        # Collect unique industries
        industries: set[str] = set()
        for reg in active_zips:
            for bt in reg.get("businessTypes", ["Restaurants"]):
                industry_key = _resolve_industry_key(bt)
                industries.add(industry_key)

        for industry_key in industries:
            try:
                enqueue_agent_task(
                    business_id=f"synthesis-industry-{industry_key}",
                    action_type="synthesis_industry",
                    task_id=f"synth-ind-{industry_key}-{week_of}",
                    metadata={"industryKey": industry_key, "weekOf": week_of},
                    dispatch_deadline_seconds=300,
                )
                triggered_industry += 1
            except Exception as e:
                logger.error(f"[Synthesis Cron] Failed to enqueue industry {industry_key}: {e}")

        # Phase 2: Zip digests (scheduled after industry digests with delay)
        for i, reg in enumerate(active_zips):
            zip_code = reg["zipCode"]
            city = reg.get("city", "")
            state = reg.get("state", "")
            county = reg.get("county", "")

            for bt in reg.get("businessTypes", ["Restaurants"]):
                industry_key = _resolve_industry_key(bt)
                try:
                    enqueue_agent_task(
                        business_id=f"synthesis-zip-{zip_code}-{bt}",
                        action_type="synthesis_zip",
                        task_id=f"synth-zip-{zip_code}-{_slugify(bt)}-{week_of}",
                        metadata={
                            "zipCode": zip_code,
                            "businessType": bt,
                            "weekOf": week_of,
                            "city": city,
                            "state": state,
                            "county": county,
                            "industryKey": industry_key,
                        },
                        dispatch_deadline_seconds=300,
                        # Delay zip digests 60s to let industry digests finish first
                        schedule_delay_seconds=60 + (i * 10),
                    )
                    triggered_zip += 1
                except Exception as e:
                    logger.error(f"[Synthesis Cron] Failed to enqueue zip {zip_code}/{bt}: {e}")

    except Exception as e:
        logger.error(f"[Synthesis Cron] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

    logger.info(
        f"[Synthesis Cron] Enqueued: {triggered_industry} industry + {triggered_zip} zip digests for {week_of}"
    )
    return {
        "weekOf": week_of,
        "triggeredIndustry": triggered_industry,
        "triggeredZip": triggered_zip,
    }


@router.post("/api/synthesis/execute")
async def execute_synthesis_task(request: Request):
    """Cloud Tasks callback — runs a single digest generation."""
    try:
        body = await request.json()
        action_type = body.get("actionType", "")
        metadata = body.get("metadata", {})

        if action_type == "synthesis_industry":
            from hephae_agents.synthesis.runner import generate_industry_digest
            result = await generate_industry_digest(
                industry_key=metadata["industryKey"],
                week_of=metadata["weekOf"],
            )
            return {"status": "completed", "type": "industry", "id": result.get("id")}

        elif action_type == "synthesis_zip":
            from hephae_agents.synthesis.runner import generate_zip_digest
            result = await generate_zip_digest(
                zip_code=metadata["zipCode"],
                business_type=metadata["businessType"],
                week_of=metadata["weekOf"],
                city=metadata.get("city", ""),
                state=metadata.get("state", ""),
                county=metadata.get("county", ""),
                industry_key=metadata.get("industryKey", ""),
            )
            return {"status": "completed", "type": "zip", "id": result.get("id")}

        else:
            return JSONResponse({"error": f"Unknown action: {action_type}"}, status_code=400)

    except Exception as e:
        logger.error(f"[Synthesis Execute] Failed: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Helpers ───────────────────────────────────────────────────────────────

import re

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


def _resolve_industry_key(business_type: str) -> str:
    """Map business type string to industry key."""
    bt = business_type.lower()
    if "restaurant" in bt or "food" in bt or "pizza" in bt or "cafe" in bt:
        return "restaurant"
    if "barber" in bt or "salon" in bt or "hair" in bt or "beauty" in bt:
        return "barber"
    if "retail" in bt or "shop" in bt or "store" in bt:
        return "retail"
    if "health" in bt or "dental" in bt or "medical" in bt:
        return "healthcare"
    return "restaurant"  # default


async def _list_active_zips() -> list[dict]:
    """List all active registered zipcodes from Firestore."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes
    return await list_registered_zipcodes(status="active")
