"""Weekly pulse cron — auto-generates pulses for all registered active zipcodes.

GET /api/cron/weekly-pulse — Triggered by Cloud Scheduler every Monday 6am ET.
Queries all active registered zipcodes and kicks off pulse generation for each
zip x businessType combination, staggering starts by 30 seconds to avoid rate limits.
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

        # Update the registered zipcode entry (single doc per zip)
        pulse_data = result.get("pulse", {})
        await update_last_pulse(
            zip_code, result["pulseId"],
            headline=pulse_data.get("headline", ""),
            insight_count=len(pulse_data.get("insights", [])),
        )

        # Auto-onboard if first successful run with quality gate
        try:
            from hephae_db.firestore.registered_zipcodes import get_registered_zipcode, approve_zipcode
            reg = await get_registered_zipcode(zip_code)
            if reg and reg.get("onboardingStatus") == "onboarding":
                insights = pulse_data.get("insights", [])
                local_briefing = pulse_data.get("localBriefing", {})
                events = local_briefing.get("thisWeekInTown", []) if isinstance(local_briefing, dict) else []
                critique_pass = result.get("diagnostics", {}).get("critiquePass", False)
                if critique_pass and len(insights) >= 3 and len(events) >= 1:
                    await approve_zipcode(zip_code)
                    logger.info(f"[PulseCron] Auto-onboarded {zip_code}")
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

    For each registered zip, iterates its businessTypes list and runs a
    pulse for each zip x businessType combination.
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

    # Build list of zip x businessType combinations to run
    to_run: list[dict] = []
    for reg in active_zips:
        zip_code = reg["zipCode"]
        business_types = reg.get("businessTypes", ["Restaurants"])

        for business_type in business_types:
            # Check if pulse already exists for this week + business type
            latest = await get_latest_pulse(zip_code, business_type)
            if latest:
                latest_week = latest.get("weekOf", "")
                if latest_week == week_of:
                    logger.info(f"[PulseCron] Skipping {zip_code}/{business_type} — pulse already exists for {week_of}")
                    skipped += 1
                    continue

            to_run.append({"zipCode": zip_code, "businessType": business_type})

    # Stagger pulse generation — 30 seconds apart, collect results
    tasks = []
    for i, entry in enumerate(to_run):
        task = asyncio.create_task(_run_single_pulse(
            zip_code=entry["zipCode"],
            business_type=entry["businessType"],
            week_of=week_of,
            delay_seconds=i * 30,
        ))
        tasks.append(task)
        triggered += 1

    # Send summary email after all pulses complete (non-blocking)
    if tasks:
        asyncio.create_task(_send_cron_summary_email(tasks, week_of, triggered, skipped))

    logger.info(f"[PulseCron] Triggered {triggered} pulses, skipped {skipped}")
    return {"triggered": triggered, "skipped": skipped}


async def _send_cron_summary_email(
    tasks: list[asyncio.Task],
    week_of: str,
    triggered: int,
    skipped: int,
):
    """Wait for all pulse tasks to complete, then send a summary email."""
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        completed = []
        failed = []
        for r in results:
            if isinstance(r, Exception):
                failed.append({"error": str(r)})
            elif isinstance(r, dict):
                if r.get("status") == "completed":
                    completed.append(r)
                else:
                    failed.append(r)

        # Build email
        subject = f"Weekly Pulse Cron — {week_of}: {len(completed)} completed, {len(failed)} failed"

        rows_html = ""
        for r in completed:
            rows_html += (
                f'<tr><td style="padding:8px 12px;border-bottom:1px solid #1e293b;">'
                f'<span style="color:#818cf8;font-family:monospace;">{r.get("zipCode", "?")}</span></td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;color:#94a3b8;">{r.get("businessType", "")}</td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;">'
                f'<span style="color:#4ade80;">&#10003; Completed</span></td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;color:#94a3b8;font-size:12px;">{r.get("pulseId", "")[:30]}</td></tr>'
            )
        for r in failed:
            rows_html += (
                f'<tr><td style="padding:8px 12px;border-bottom:1px solid #1e293b;">'
                f'<span style="color:#818cf8;font-family:monospace;">{r.get("zipCode", "?")}</span></td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;color:#94a3b8;">{r.get("businessType", "")}</td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;">'
                f'<span style="color:#f87171;">&#10007; Failed</span></td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #1e293b;color:#f87171;font-size:12px;">{r.get("error", "")[:60]}</td></tr>'
            )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
<tr><td align="center" style="padding:40px 20px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:16px 16px 0 0;padding:24px 32px;text-align:center;">
  <div style="font-size:22px;font-weight:800;color:#fff;">Hephae Weekly Pulse</div>
  <div style="font-size:13px;color:rgba(255,255,255,0.7);">Cron Run Summary — {week_of}</div>
</td></tr>
<tr><td style="background:#1e293b;padding:24px 32px;border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);">
  <div style="display:flex;gap:16px;margin-bottom:20px;">
    <div style="background:#0f172a;border-radius:8px;padding:12px 16px;flex:1;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#4ade80;">{len(completed)}</div>
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;">Completed</div>
    </div>
    <div style="background:#0f172a;border-radius:8px;padding:12px 16px;flex:1;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#f87171;">{len(failed)}</div>
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;">Failed</div>
    </div>
    <div style="background:#0f172a;border-radius:8px;padding:12px 16px;flex:1;text-align:center;">
      <div style="font-size:24px;font-weight:700;color:#94a3b8;">{skipped}</div>
      <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;">Skipped</div>
    </div>
  </div>
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;color:#e2e8f0;">
    <tr style="color:#64748b;font-size:11px;text-transform:uppercase;">
      <td style="padding:8px 12px;border-bottom:1px solid #334155;">Zip</td>
      <td style="padding:8px 12px;border-bottom:1px solid #334155;">Type</td>
      <td style="padding:8px 12px;border-bottom:1px solid #334155;">Status</td>
      <td style="padding:8px 12px;border-bottom:1px solid #334155;">Details</td>
    </tr>
    {rows_html}
  </table>
</td></tr>
<tr><td style="background:#0f172a;border-radius:0 0 16px 16px;padding:16px 32px;text-align:center;border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);border-bottom:1px solid rgba(255,255,255,0.08);">
  <div style="font-size:11px;color:#64748b;">Hephae Forge — Automated Weekly Intelligence</div>
</td></tr>
</table>
</td></tr></table>
</body></html>"""

        text = f"Weekly Pulse Cron — {week_of}: {len(completed)} completed, {len(failed)} failed, {skipped} skipped"

        from hephae_common.email import send_email
        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if recipients:
            email_list = [e.strip() for e in recipients.split(",") if e.strip()]
            if email_list:
                await send_email(to=email_list, subject=subject, text=text, html_content=html)
                logger.info(f"[PulseCron] Summary email sent to {len(email_list)} recipients")
        else:
            logger.warning("[PulseCron] No email recipients configured for cron summary")

    except Exception as e:
        logger.error(f"[PulseCron] Failed to send summary email: {e}")


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
                "businessTypes": z.get("businessTypes", ["Restaurants"]),
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
