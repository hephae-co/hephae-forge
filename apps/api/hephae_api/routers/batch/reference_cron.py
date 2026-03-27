"""Research Reference Harvester cron — weekly external research collection.

GET /api/cron/reference-harvest

Runs Friday 6:00 AM ET (11:00 UTC) — before the weekend blog/outreach cycle.
Harvests authoritative external research (Deloitte, NRA, USDA, govt agencies,
trade press) on topics relevant to Hephae: restaurant margins, food costs,
commodity prices, small business profitability, restaurant tech, labor costs.

Stores clean structured references in Firestore `research_references` collection
for use by blogs, outreach agents, and pulse synthesis.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reference-cron"])


@router.get("/api/cron/reference-harvest")
async def reference_harvest_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Harvest weekly research references from authoritative external sources.

    Idempotent — skips URLs already stored. Safe to re-run.
    """
    # Auth
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_agents.research.reference_harvester import run_weekly_harvest

    logger.info("[ReferenceCron] Starting weekly research harvest")
    result = await run_weekly_harvest()
    logger.info(
        f"[ReferenceCron] Done — {result['harvested']} harvested, "
        f"{result['saved']} saved, topics: {result['by_topic']}"
    )

    await _send_summary_email(result)

    return {"success": True, **result}


async def _send_summary_email(result: dict):
    """Send a summary email to admins after reference harvest cron completes."""
    import asyncio

    try:
        from hephae_common.email import send_email

        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if not recipients:
            logger.warning("[ReferenceCron] No email recipients configured")
            return

        email_list = [e.strip() for e in recipients.split(",") if e.strip()]
        if not email_list:
            return

        harvested = result.get("harvested", 0)
        saved = result.get("saved", 0)
        by_topic = result.get("by_topic", {})

        subject = f"Reference Harvest Cron — {harvested} harvested, {saved} saved"

        topic_rows = ""
        for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
            topic_rows += f"""<tr>
                <td style="padding:8px;border-bottom:1px solid #eee">{topic}</td>
                <td style="padding:8px;border-bottom:1px solid #eee">{count}</td>
            </tr>"""

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:600px">
            <h2 style="color:#7c3aed">Reference Harvest Cron Complete</h2>
            <p><strong>{harvested}</strong> references harvested, <strong>{saved}</strong> new saved</p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px">
                <tr style="background:#f9fafb">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Topic</th>
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #e5e7eb">Count</th>
                </tr>
                {topic_rows if topic_rows else '<tr><td colspan="2" style="padding:8px;color:#6b7280">No topics</td></tr>'}
            </table>
            <p style="margin-top:16px;font-size:13px;color:#6b7280">
                References stored in Firestore <code>research_references</code> collection.
            </p>
        </div>"""

        text = (
            f"Reference Harvest Cron: {harvested} harvested, {saved} saved. "
            + ", ".join(f"{t}={c}" for t, c in by_topic.items())
        )

        last_err = None
        for attempt in range(3):
            try:
                await send_email(to=email_list, subject=subject, text=text, html_content=html)
                logger.info(f"[ReferenceCron] Summary email sent to {len(email_list)} recipients")
                return
            except Exception as send_err:
                last_err = send_err
                logger.warning(f"[ReferenceCron] Email attempt {attempt + 1}/3 failed: {send_err}")
                if attempt < 2:
                    await asyncio.sleep(5)

        logger.error(f"[ReferenceCron] All email attempts failed: {last_err}")

    except Exception as e:
        logger.error(f"[ReferenceCron] Failed to send summary email: {e}")
