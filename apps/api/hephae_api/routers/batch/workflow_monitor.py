"""Workflow monitor cron — detects completed/failed workflows and sends digest email."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow-monitor"])

# Phases we report on (terminal + queued for visibility)
_TERMINAL = {"completed", "failed", "approval"}

# Configurable window (minutes) — should match Cloud Scheduler interval
_DEFAULT_WINDOW_MINUTES = 30


def _get_notify_emails() -> list[str]:
    """Resolve all emails to send digests to."""
    explicit = os.environ.get("MONITOR_NOTIFY_EMAILS", "")
    if explicit:
        return [e.strip() for e in explicit.split(",") if e.strip()]
    allowlist = settings.ADMIN_EMAIL_ALLOWLIST
    if allowlist:
        return [e.strip() for e in allowlist.split(",") if e.strip()]
    return []


def _phase_icon(phase: str) -> str:
    if phase == "completed":
        return "✅"
    if phase == "failed":
        return "❌"
    if phase == "approval":
        return "⏸️"
    return "🔄"


def _build_digest_html(workflows: list[dict[str, Any]]) -> str:
    """Build a compact HTML digest email."""
    rows = []
    for wf in workflows:
        icon = _phase_icon(wf["phase"])
        wf_id_short = (wf.get("id") or "?")[:12]
        label = f"{wf.get('businessType', '?')} in {wf.get('zipCode', '?')}"
        if wf.get("county"):
            label = f"{wf.get('businessType', '?')} in {wf['county']}"

        progress = wf.get("progress", {})
        total = progress.get("totalBusinesses", 0)
        passed = progress.get("qualityPassed", 0)
        failed_eval = progress.get("qualityFailed", 0)
        analysis_done = progress.get("analysisComplete", 0)

        detail = f"{total} businesses"
        if wf["phase"] == "completed" or wf["phase"] == "approval":
            detail += f" · {passed} passed eval, {failed_eval} failed"
        elif wf["phase"] == "failed":
            detail += f" · {analysis_done} analyzed"

        error_line = ""
        if wf.get("lastError"):
            err = wf["lastError"][:120]
            error_line = f'<div style="color:#f87171;font-size:12px;margin-top:4px;">→ {err}</div>'

        skill_cmd = f"/hephae-debug-job {wf_id_short}"

        rows.append(f"""
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:16px;margin-bottom:2px;">{icon} <strong>{label}</strong></div>
            <div style="font-size:13px;color:#94a3b8;">{detail}</div>
            {error_line}
            <div style="font-size:11px;color:#64748b;margin-top:4px;">
              ID: <code>{wf_id_short}</code> · Debug: <code>{skill_cmd}</code>
            </div>
          </td>
        </tr>""")

    rows_html = "\n".join(rows)
    completed = sum(1 for w in workflows if w["phase"] == "completed")
    failed = sum(1 for w in workflows if w["phase"] == "failed")
    paused = sum(1 for w in workflows if w["phase"] == "approval")

    subject_parts = []
    if completed:
        subject_parts.append(f"{completed} completed")
    if failed:
        subject_parts.append(f"{failed} failed")
    if paused:
        subject_parts.append(f"{paused} awaiting approval")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e2e8f0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
    <tr><td align="center" style="padding:32px 16px;">
      <table width="560" style="max-width:560px;width:100%;">
        <tr><td style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:12px 12px 0 0;padding:20px 24px;text-align:center;">
          <div style="font-size:20px;font-weight:800;color:#fff;">Hephae Workflow Digest</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:4px;">{', '.join(subject_parts)}</div>
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-top:none;">
          <table width="100%" cellpadding="0" cellspacing="0">
            {rows_html}
          </table>
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 12px 12px;padding:16px 24px;text-align:center;">
          <div style="font-size:11px;color:rgba(226,232,240,0.3);">
            Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a> · Workflow Monitor
          </div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


@router.get("/api/cron/workflow-monitor")
async def workflow_monitor(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
    window: int = Query(_DEFAULT_WINDOW_MINUTES, description="Lookback window in minutes"),
):
    """Check for recently completed/failed workflows and send digest email.

    Called by Cloud Scheduler every 30 minutes.
    Auth: CRON_SECRET via X-Cron-Secret header (preferred) or Authorization header.
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.workflows import list_workflows
    from hephae_common.models import WorkflowDocument
    from hephae_common.email import send_email

    cutoff = datetime.utcnow() - timedelta(minutes=window)

    # Fetch recent workflows (more than we need, filter in Python)
    all_workflows = await list_workflows(limit=50, model_class=WorkflowDocument)

    # Filter to workflows that reached a terminal phase within the window
    recent = []
    for wf in all_workflows:
        if wf.phase.value not in _TERMINAL:
            continue
        if wf.updatedAt and wf.updatedAt >= cutoff:
            recent.append({
                "id": wf.id,
                "phase": wf.phase.value,
                "zipCode": wf.zipCode,
                "businessType": wf.businessType or "Unknown",
                "county": wf.county,
                "lastError": wf.lastError,
                "progress": wf.progress.model_dump() if wf.progress else {},
                "updatedAt": wf.updatedAt.isoformat() if wf.updatedAt else "",
            })

    if not recent:
        logger.info(f"[WorkflowMonitor] No terminal workflows in last {window}min")
        return {"digested": 0, "message": "Nothing to report"}

    # Build and send digest
    notify_emails = _get_notify_emails()
    if not notify_emails:
        logger.warning("[WorkflowMonitor] No MONITOR_NOTIFY_EMAILS or ADMIN_EMAIL_ALLOWLIST configured")
        return {"digested": len(recent), "emailed": False, "reason": "no_email_configured", "workflows": recent}

    completed = sum(1 for w in recent if w["phase"] == "completed")
    failed = sum(1 for w in recent if w["phase"] == "failed")
    paused = sum(1 for w in recent if w["phase"] == "approval")

    subject_parts = []
    if completed:
        subject_parts.append(f"{completed} completed")
    if failed:
        subject_parts.append(f"{failed} failed")
    if paused:
        subject_parts.append(f"{paused} awaiting approval")
    subject = f"Hephae Workflow Digest — {', '.join(subject_parts)}"

    # Plain text fallback
    text_lines = [subject, ""]
    for wf in recent:
        icon = _phase_icon(wf["phase"])
        label = f"{wf['businessType']} in {wf.get('county') or wf['zipCode']}"
        text_lines.append(f"{icon} {label} ({wf['phase']})")
        if wf.get("lastError"):
            text_lines.append(f"   → {wf['lastError'][:120]}")
        text_lines.append(f"   Debug: /hephae-debug-job {(wf['id'] or '?')[:12]}")
        text_lines.append("")

    html = _build_digest_html(recent)
    text = "\n".join(text_lines)

    # Send single email to all recipients (avoids Resend rate limits)
    try:
        email_id = await send_email(
            to=notify_emails,
            subject=subject,
            text=text,
            html_content=html,
        )
        logger.info(f"[WorkflowMonitor] Digest sent to {notify_emails} (email={email_id})")
        return {
            "digested": len(recent),
            "emailed": True,
            "sentTo": notify_emails,
            "emailId": email_id,
            "completed": completed,
            "failed": failed,
            "paused": paused,
        }
    except Exception as e:
        logger.error(f"[WorkflowMonitor] Failed to send digest: {e}")
        return {
            "digested": len(recent),
            "emailed": False,
            "error": str(e),
            "completed": completed,
            "failed": failed,
            "paused": paused,
        }
