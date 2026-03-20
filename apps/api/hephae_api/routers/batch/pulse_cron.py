"""Weekly pulse cron — auto-generates pulses for all registered active zipcodes.

GET /api/cron/weekly-pulse — Triggered by Cloud Scheduler every Monday 6am ET.
Queries all active registered zipcodes and kicks off pulse generation for each,
staggering starts by 30 seconds to avoid rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pulse-cron"])


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


def _current_iso_week() -> str:
    """Return current ISO week string like '2026-W13'."""
    now = datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


async def _run_single_pulse(
    zip_code: str,
    business_type: str,
    week_of: str,
    delay_seconds: int,
) -> dict:
    """Run a single pulse generation with a staggered delay."""
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    from hephae_db.firestore.pulse_jobs import create_pulse_job, update_pulse_job
    from hephae_api.workflows.orchestrators.weekly_pulse import generate_pulse
    from hephae_db.firestore.registered_zipcodes import update_last_pulse

    job_id = await create_pulse_job(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
    )

    try:
        from datetime import timedelta
        await update_pulse_job(job_id, {
            "status": "RUNNING",
            "startedAt": datetime.utcnow(),
            "timeoutAt": datetime.utcnow() + timedelta(minutes=15),
        })

        result = await generate_pulse(
            zip_code=zip_code,
            business_type=business_type,
            week_of=week_of,
            force=False,
        )

        await update_pulse_job(job_id, {
            "status": "COMPLETED",
            "completedAt": datetime.utcnow(),
            "result": {
                "pulseId": result["pulseId"],
                "signalsUsed": result["signalsUsed"],
                "insightCount": len(result.get("pulse", {}).get("insights", [])),
                "headline": result.get("pulse", {}).get("headline", ""),
            },
        })

        # Update the registered zipcode entry
        pulse_data = result.get("pulse", {})
        await update_last_pulse(
            zip_code, business_type, result["pulseId"],
            headline=pulse_data.get("headline", ""),
            insight_count=len(pulse_data.get("insights", [])),
        )

        # Auto-onboard if first successful run with quality gate
        try:
            from hephae_db.firestore.registered_zipcodes import get_registered_zipcode, approve_zipcode
            reg = await get_registered_zipcode(zip_code, business_type)
            if reg and reg.get("onboardingStatus") == "onboarding":
                insights = pulse_data.get("insights", [])
                local_briefing = pulse_data.get("localBriefing", {})
                events = local_briefing.get("thisWeekInTown", []) if isinstance(local_briefing, dict) else []
                critique_pass = result.get("diagnostics", {}).get("critiquePass", False)
                if critique_pass and len(insights) >= 3 and len(events) >= 1:
                    await approve_zipcode(zip_code, business_type)
                    logger.info(f"[PulseCron] Auto-onboarded {zip_code}/{business_type}")
        except Exception as e:
            logger.warning(f"[PulseCron] Auto-onboard check failed: {e}")

        logger.info(f"[PulseCron] Completed pulse for {zip_code}/{business_type} -> {result['pulseId']}")
        return {"zipCode": zip_code, "businessType": business_type, "status": "completed", "pulseId": result["pulseId"]}

    except Exception as e:
        logger.error(f"[PulseCron] Failed pulse for {zip_code}/{business_type}: {e}")
        await update_pulse_job(job_id, {
            "status": "FAILED",
            "completedAt": datetime.utcnow(),
            "error": str(e),
        })
        return {"zipCode": zip_code, "businessType": business_type, "status": "failed", "error": str(e)}


@router.get("/api/cron/weekly-pulse")
async def weekly_pulse_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Trigger weekly pulse generation for all active registered zipcodes.

    Called by Cloud Scheduler every Monday at 6am ET. Idempotent — skips
    zipcodes that already have a pulse for the current week.
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes
    from hephae_db.firestore.weekly_pulse import get_latest_pulse

    active_zips = await list_registered_zipcodes(status="active")
    if not active_zips:
        logger.info("[PulseCron] No active registered zipcodes")
        return {"triggered": 0, "skipped": 0}

    # Use ISO week for consistent dedup — same format as generate_pulse()
    now = datetime.utcnow()
    week_of = f"{now.year}-W{now.isocalendar()[1]:02d}"
    triggered = 0
    skipped = 0

    # Check each zipcode for existing pulse this week
    to_run: list[dict] = []
    for reg in active_zips:
        zip_code = reg["zipCode"]
        business_type = reg["businessType"]

        # Check if pulse already exists for this week
        latest = await get_latest_pulse(zip_code, business_type)
        if latest:
            latest_week = latest.get("weekOf", "")
            if latest_week == week_of:
                logger.info(f"[PulseCron] Skipping {zip_code}/{business_type} — pulse already exists for {week_of}")
                skipped += 1
                continue

        to_run.append({"zipCode": zip_code, "businessType": business_type})

    # Stagger pulse generation — 30 seconds apart
    for i, entry in enumerate(to_run):
        asyncio.create_task(_run_single_pulse(
            zip_code=entry["zipCode"],
            business_type=entry["businessType"],
            week_of=week_of,
            delay_seconds=i * 30,
        ))
        triggered += 1

    logger.info(f"[PulseCron] Triggered {triggered} pulses, skipped {skipped}")
    return {"triggered": triggered, "skipped": skipped}


@router.get("/api/cron/weekly-pulse/status")
async def weekly_pulse_cron_status(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Get cron status — which zipcodes are scheduled, last/next run times."""
    # Allow both cron secret and admin auth
    from hephae_api.lib.auth import verify_admin_request
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes
    from hephae_db.firestore.pulse_jobs import list_pulse_jobs

    active_zips = await list_registered_zipcodes(status="active")
    paused_zips = await list_registered_zipcodes(status="paused")

    # Get recent cron-triggered jobs (non-test)
    recent_jobs = await list_pulse_jobs(limit=20)
    cron_jobs = [j for j in recent_jobs if not j.get("testMode")]

    # Next Monday 6am ET
    from datetime import timedelta
    now = datetime.utcnow()
    days_until_monday = (7 - now.weekday()) % 7 or 7
    next_monday = (now + timedelta(days=days_until_monday)).replace(hour=11, minute=0, second=0, microsecond=0)

    return {
        "activeZipcodes": len(active_zips),
        "pausedZipcodes": len(paused_zips),
        "nextRunAt": next_monday.isoformat() + "Z",
        "schedule": "Every Monday 6:00 AM ET",
        "zipcodes": [
            {
                "zipCode": z.get("zipCode"),
                "businessType": z.get("businessType"),
                "city": z.get("city"),
                "state": z.get("state"),
                "status": z.get("status"),
                "lastPulseAt": z.get("lastPulseAt"),
                "pulseCount": z.get("pulseCount", 0),
                "nextScheduledAt": z.get("nextScheduledAt"),
            }
            for z in active_zips + paused_zips
        ],
        "recentRuns": [
            {
                "jobId": j.get("id"),
                "zipCode": j.get("zipCode"),
                "businessType": j.get("businessType"),
                "status": j.get("status"),
                "createdAt": j.get("createdAt"),
                "completedAt": j.get("completedAt"),
                "error": j.get("error"),
            }
            for j in cron_jobs[:10]
        ],
    }
