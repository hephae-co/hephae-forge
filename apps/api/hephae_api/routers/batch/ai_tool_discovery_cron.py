"""AI Tool Discovery cron — generates AI tool profiles for all registered industries.

GET /api/cron/ai-tool-discovery — Triggered by Cloud Scheduler Tuesday 7 AM ET.
Runs after Tech Intelligence (Sun 1 AM) and Industry Pulse (Sun 3 AM).
Runs sequentially (not parallel) to avoid Google Search rate limits.
Idempotent — skips verticals that already have a run for the current ISO week.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai-tool-discovery-cron"])


@router.get("/api/cron/ai-tool-discovery")
async def ai_tool_discovery_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Generate AI tool discovery profiles for all registered industries."""
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_api.workflows.orchestrators.industries import all_industries
    from hephae_api.workflows.orchestrators.ai_tool_discovery import generate_ai_tool_discovery

    industries = all_industries()
    results = []
    failed = 0

    for industry in industries:
        try:
            logger.info(f"[AiToolDiscoveryCron] Running for {industry.id}")
            result = await generate_ai_tool_discovery(industry.id, force=False)
            if result.get("error"):
                failed += 1
                results.append({
                    "vertical": industry.id,
                    "status": "failed",
                    "error": result["error"],
                })
            elif result.get("skipped"):
                results.append({
                    "vertical": industry.id,
                    "status": "skipped",
                    "reason": "already_exists_this_week",
                })
            else:
                results.append({
                    "vertical": industry.id,
                    "status": "generated",
                    "totalToolsFound": result.get("totalToolsFound", 0),
                    "newToolsCount": result.get("newToolsCount", 0),
                    "freeToolsCount": result.get("freeToolsCount", 0),
                    "weeklyHighlight": result.get("weeklyHighlight", {}).get("title", ""),
                })
        except Exception as e:
            logger.error(f"[AiToolDiscoveryCron] Failed for {industry.id}: {e}")
            failed += 1
            results.append({
                "vertical": industry.id,
                "status": "failed",
                "error": str(e),
            })

    generated = len([r for r in results if r.get("status") == "generated"])
    skipped = len([r for r in results if r.get("status") == "skipped"])

    logger.info(
        f"[AiToolDiscoveryCron] Complete: "
        f"{generated} generated, {skipped} skipped, {failed} failed"
    )

    await _send_summary_email(results, generated, skipped, failed)

    return {
        "success": True,
        "generated": generated,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }


async def _send_summary_email(results: list[dict], generated: int, skipped: int, failed: int):
    """Send a summary email after AI tool discovery cron completes (always — even on failure)."""
    try:
        from hephae_common.email import send_email

        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if not recipients:
            return
        email_list = [e.strip() for e in recipients.split(",") if e.strip()]
        if not email_list:
            return

        subject = f"AI Tool Discovery Cron — {generated} generated, {skipped} skipped, {failed} failed"

        rows = ""
        for r in results:
            if r["status"] == "generated":
                status_color = "#22c55e"
                status_icon = "&#10003;"
                detail = (
                    f'{r.get("totalToolsFound", 0)} tools, '
                    f'{r.get("newToolsCount", 0)} new, '
                    f'{r.get("freeToolsCount", 0)} free'
                )
                if r.get("weeklyHighlight"):
                    detail += f' | {r["weeklyHighlight"][:60]}'
            elif r["status"] == "skipped":
                status_color = "#94a3b8"
                status_icon = "&#8594;"
                detail = "already exists this week"
            else:
                status_color = "#ef4444"
                status_icon = "&#10007;"
                detail = r.get("error", "Unknown error")[:100]

            rows += (
                f'<tr>'
                f'<td style="padding:8px;border-bottom:1px solid #eee">{r.get("vertical", "?")}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #eee;color:{status_color}">{status_icon} {r["status"]}</td>'
                f'<td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">{detail}</td>'
                f'</tr>'
            )

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:600px">
            <h2 style="color:#8b5cf6">AI Tool Discovery Cron Complete</h2>
            <p><strong>{generated}</strong> generated, <strong>{skipped}</strong> skipped, <strong>{failed}</strong> failed</p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px">
                <tr style="background:#f9fafb">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Industry</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Status</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Details</th>
                </tr>
                {rows}
            </table>
        </div>"""

        text = (
            f"AI Tool Discovery Cron: {generated} generated, {skipped} skipped, {failed} failed. "
            + ", ".join(f'{r["vertical"]}={r["status"]}' for r in results)
        )

        await send_email(to=email_list, subject=subject, text=text, html_content=html)
        logger.info(f"[AiToolDiscoveryCron] Summary email sent to {len(email_list)} recipients")

    except Exception as e:
        logger.error(f"[AiToolDiscoveryCron] Failed to send summary email: {e}")
