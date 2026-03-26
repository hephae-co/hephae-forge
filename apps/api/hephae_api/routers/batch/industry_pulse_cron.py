"""Industry pulse cron — generates national-level pulse for each registered industry.

Runs Sunday 3:00 AM ET (08:00 UTC), BEFORE the zip-level pulse cron (Monday 11:00 UTC).
Each industry pulse fetches BLS CPI, USDA prices, FDA recalls, computes
impact multipliers, matches playbooks, and generates a national trend summary.

Zip-level pulses then load this pre-computed data instead of re-fetching.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(tags=["industry-pulse-cron"])


@router.get("/api/cron/industry-pulse")
async def industry_pulse_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Generate industry pulses for all active registered industries.

    Called by Cloud Scheduler. Idempotent — skips industries that already
    have a pulse for this week.
    """
    from hephae_api.config import settings

    # Auth check
    cron_secret = settings.CRON_SECRET
    if cron_secret:
        token = (x_cron_secret or "").removeprefix("Bearer ").strip()
        if not token:
            token = (authorization or "").removeprefix("Bearer ").strip()
        if token != cron_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.registered_industries import (
        list_registered_industries,
        update_last_industry_pulse,
    )
    from hephae_api.workflows.orchestrators.industry_pulse import generate_industry_pulse

    industries = await list_registered_industries(status="active")
    if not industries:
        logger.info("[IndustryPulseCron] No active industries registered")
        await _send_summary_email([], 0, 0)
        return {"success": True, "message": "No active industries", "generated": 0}

    results = []
    for ind in industries:
        industry_key = ind.get("industryKey", "")
        try:
            logger.info(f"[IndustryPulseCron] Generating pulse for {industry_key}")
            pulse = await generate_industry_pulse(industry_key)
            pulse_id = pulse.get("id", "")
            await update_last_industry_pulse(industry_key, pulse_id)
            results.append({
                "industryKey": industry_key,
                "displayName": ind.get("displayName", industry_key),
                "status": "generated",
                "pulseId": pulse_id,
                "signalCount": len(pulse.get("signalsUsed", [])),
                "playbooksMatched": len(pulse.get("nationalPlaybooks", [])),
                "trendPreview": (pulse.get("trendSummary") or "")[:200],
            })
        except Exception as e:
            logger.error(f"[IndustryPulseCron] Failed for {industry_key}: {e}")
            results.append({
                "industryKey": industry_key,
                "displayName": ind.get("displayName", industry_key),
                "status": "failed",
                "error": str(e)[:200],
            })

    generated = sum(1 for r in results if r["status"] == "generated")
    failed = sum(1 for r in results if r["status"] == "failed")
    logger.info(f"[IndustryPulseCron] Done: {generated} generated, {failed} failed")

    # Send summary email
    await _send_summary_email(results, generated, failed)

    return {
        "success": True,
        "generated": generated,
        "failed": failed,
        "results": results,
    }


async def _send_summary_email(results: list[dict], generated: int, failed: int):
    """Send a summary email to admins after industry pulse cron completes."""
    import asyncio

    try:
        from hephae_api.config import settings
        from hephae_common.email import send_email

        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if not recipients:
            logger.warning("[IndustryPulseCron] No email recipients configured")
            return

        email_list = [e.strip() for e in recipients.split(",") if e.strip()]
        if not email_list:
            return

        subject = f"Industry Pulse Cron — {generated} generated, {failed} failed"

        # Build HTML table
        rows = ""
        for r in results:
            status_color = "#22c55e" if r["status"] == "generated" else "#ef4444"
            status_icon = "&#10003;" if r["status"] == "generated" else "&#10007;"
            detail = ""
            if r["status"] == "generated":
                detail = f'{r.get("signalCount", 0)} signals, {r.get("playbooksMatched", 0)} playbooks'
            else:
                detail = r.get("error", "Unknown error")[:100]

            rows += f"""<tr>
                <td style="padding:8px;border-bottom:1px solid #eee">{r.get("displayName", r["industryKey"])}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;color:{status_color}">{status_icon} {r["status"]}</td>
                <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">{detail}</td>
            </tr>"""

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:600px">
            <h2 style="color:#d97706">Industry Pulse Cron Complete</h2>
            <p><strong>{generated}</strong> industries generated, <strong>{failed}</strong> failed</p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px">
                <tr style="background:#f9fafb">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Industry</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Status</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Details</th>
                </tr>
                {rows}
            </table>
            <p style="margin-top:16px;font-size:13px;color:#6b7280">
                Zip-level pulses will use this data on the next cron run.
            </p>
        </div>"""

        text = f"Industry Pulse Cron: {generated} generated, {failed} failed. " + \
               ", ".join(f'{r["industryKey"]}={r["status"]}' for r in results)

        # Retry up to 3 times on transient errors (Resend SSL drops, etc.)
        last_err = None
        for attempt in range(3):
            try:
                await send_email(to=email_list, subject=subject, text=text, html_content=html)
                logger.info(f"[IndustryPulseCron] Summary email sent to {len(email_list)} recipients")
                return
            except Exception as send_err:
                last_err = send_err
                logger.warning(f"[IndustryPulseCron] Email attempt {attempt + 1}/3 failed: {send_err}")
                if attempt < 2:
                    await asyncio.sleep(5)

        logger.error(f"[IndustryPulseCron] All email attempts failed: {last_err}")

    except Exception as e:
        logger.error(f"[IndustryPulseCron] Failed to send summary email: {e}")
