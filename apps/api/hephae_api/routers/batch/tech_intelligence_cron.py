"""Tech Intelligence cron — generates technology landscape profiles for all registered industries.

GET /api/cron/tech-intelligence — Triggered by Cloud Scheduler Sunday 1 AM ET.
Runs TechScout pipeline for each registered industry with bounded concurrency
(semaphore=5) to stay within Cloud Run timeout while respecting Search rate limits.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tech-intelligence-cron"])


@router.get("/api/cron/tech-intelligence")
async def tech_intelligence_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Generate technology intelligence profiles for all registered industries."""
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_api.workflows.orchestrators.industries import all_industries
    from hephae_api.workflows.orchestrators.tech_intelligence import generate_tech_intelligence

    industries = all_industries()
    sem = asyncio.Semaphore(5)

    async def _run_one(industry):
        async with sem:
            try:
                logger.info(f"[TechIntelCron] Running tech scout for {industry.id}")
                result = await generate_tech_intelligence(industry.id)
                if result.get("error"):
                    return {"vertical": industry.id, "status": "failed", "error": result["error"]}
                return {
                    "vertical": industry.id,
                    "status": "generated",
                    "aiOpportunities": len(result.get("aiOpportunities", [])),
                    "platforms": len(result.get("platforms", {})),
                    "weeklyHighlight": result.get("weeklyHighlight", {}).get("title", ""),
                }
            except Exception as e:
                logger.error(f"[TechIntelCron] Failed for {industry.id}: {e}")
                return {"vertical": industry.id, "status": "failed", "error": str(e)}

    results = await asyncio.gather(*[_run_one(ind) for ind in industries])
    results = list(results)
    failed = sum(1 for r in results if r["status"] == "failed")

    generated = len(results) - failed
    logger.info(f"[TechIntelCron] Complete: {generated} succeeded, {failed} failed")

    await _send_summary_email(results, generated, failed)

    return {
        "success": True,
        "generated": generated,
        "failed": failed,
        "results": results,
    }


async def _send_summary_email(results: list[dict], generated: int, failed: int):
    """Send a summary email after tech intelligence cron completes (always — even on failure)."""
    import asyncio

    try:
        from hephae_common.email import send_email

        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if not recipients:
            return
        email_list = [e.strip() for e in recipients.split(",") if e.strip()]
        if not email_list:
            return

        subject = f"Tech Intelligence Cron — {generated} generated, {failed} failed"

        rows = ""
        for r in results:
            status_color = "#22c55e" if r["status"] == "generated" else "#ef4444"
            status_icon = "&#10003;" if r["status"] == "generated" else "&#10007;"
            detail = ""
            if r["status"] == "generated":
                detail = f'{r.get("aiOpportunities", 0)} AI opps, {r.get("platforms", 0)} platforms'
                if r.get("weeklyHighlight"):
                    detail += f' | {r["weeklyHighlight"][:60]}'
            else:
                detail = r.get("error", "Unknown error")[:100]
            rows += (
                f'<tr>'
                f'<td style="padding:8px;border-bottom:1px solid #eee">{r.get("vertical", "?")}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #eee;color:{status_color}">{status_icon} {r["status"]}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">{detail}</td>'
                f'</tr>'
            )

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:600px">
            <h2 style="color:#6366f1">Tech Intelligence Cron Complete</h2>
            <p><strong>{generated}</strong> industries generated, <strong>{failed}</strong> failed</p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px">
                <tr style="background:#f9fafb">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Industry</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Status</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Details</th>
                </tr>
                {rows}
            </table>
        </div>"""

        text = f"Tech Intelligence Cron: {generated} generated, {failed} failed. " + \
               ", ".join(f'{r["vertical"]}={r["status"]}' for r in results)

        last_err = None
        for attempt in range(3):
            try:
                await send_email(to=email_list, subject=subject, text=text, html_content=html)
                logger.info(f"[TechIntelCron] Summary email sent to {len(email_list)} recipients")
                return
            except Exception as send_err:
                last_err = send_err
                logger.warning(f"[TechIntelCron] Email attempt {attempt + 1}/3 failed: {send_err}")
                if attempt < 2:
                    await asyncio.sleep(5)

        logger.error(f"[TechIntelCron] All email attempts failed: {last_err}")

    except Exception as e:
        logger.error(f"[TechIntelCron] Failed to send summary email: {e}")
