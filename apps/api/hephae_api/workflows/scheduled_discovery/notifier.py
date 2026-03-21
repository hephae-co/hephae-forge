"""Email notification on marketing discovery job completion."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def send_job_completion_email(
    job: dict[str, Any],
    progress: dict[str, Any],
    skip_sample: list[str],
) -> None:
    """Send a completion summary email to the job's notify_email address."""
    try:
        from hephae_common.email import send_email
    except ImportError:
        logger.warning("[Notifier] hephae_common.email not available — skipping notification")
        return

    notify_email = job.get("notifyEmail", "admin@hephae.co")
    job_name = job.get("name", "Discovery Job")
    status = job.get("status", "completed")

    total = progress.get("totalBusinesses", 0)
    qualified = progress.get("qualified", 0)
    skipped = progress.get("skipped", 0)
    failed = progress.get("failed", 0)
    zips_done = progress.get("completedZips", 0)
    zips_total = progress.get("totalZips", 0)

    status_color = "#4ade80" if status == "completed" else "#f87171"
    status_label = status.upper()

    skip_list_html = ""
    if skip_sample:
        items = "".join(f"<li style='margin:4px 0;color:#94a3b8;'>{s}</li>" for s in skip_sample[:10])
        skip_list_html = f"""
        <div style="margin-top:24px;">
          <div style="font-size:13px;color:#64748b;margin-bottom:8px;">Sample skip reasons:</div>
          <ul style="margin:0;padding-left:20px;">{items}</ul>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
  <tr><td align="center" style="padding:40px 20px;">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
      <tr>
        <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:28px 36px;">
          <div style="font-size:22px;font-weight:800;color:#fff;">Hephae</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:2px;">Marketing Discovery — Job Complete</div>
        </td>
      </tr>
      <tr>
        <td style="background:#1e293b;border:1px solid #334155;border-top:none;border-radius:0 0 16px 16px;padding:36px;">
          <div style="font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:4px;">{job_name}</div>
          <div style="display:inline-block;padding:4px 12px;border-radius:20px;background:{status_color}22;color:{status_color};font-size:12px;font-weight:600;margin-bottom:28px;">{status_label}</div>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
            <tr>
              <td style="padding:12px;background:#0f172a;border-radius:8px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:800;color:#a78bfa;">{zips_done}/{zips_total}</div>
                <div style="font-size:11px;color:#64748b;margin-top:4px;">ZIP codes</div>
              </td>
              <td style="width:8px;"></td>
              <td style="padding:12px;background:#0f172a;border-radius:8px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:800;color:#f1f5f9;">{total}</div>
                <div style="font-size:11px;color:#64748b;margin-top:4px;">discovered</div>
              </td>
              <td style="width:8px;"></td>
              <td style="padding:12px;background:#0f172a;border-radius:8px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:800;color:#4ade80;">{qualified}</div>
                <div style="font-size:11px;color:#64748b;margin-top:4px;">qualified</div>
              </td>
              <td style="width:8px;"></td>
              <td style="padding:12px;background:#0f172a;border-radius:8px;text-align:center;width:25%;">
                <div style="font-size:28px;font-weight:800;color:#94a3b8;">{skipped}</div>
                <div style="font-size:11px;color:#64748b;margin-top:4px;">skipped</div>
              </td>
            </tr>
          </table>

          {f'<div style="padding:12px;background:#7f1d1d22;border:1px solid #7f1d1d;border-radius:8px;color:#fca5a5;font-size:13px;">{failed} businesses failed — check Cloud Run logs for details.</div>' if failed else ''}
          {skip_list_html}

          <div style="margin-top:28px;padding-top:20px;border-top:1px solid #334155;font-size:12px;color:#475569;text-align:center;">
            Hephae · admin@hephae.co · View results in the <a href="https://admin.hephae.co" style="color:#818cf8;">admin dashboard</a>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""

    subject = f"[Hephae] Marketing discovery '{job_name}' — {qualified} businesses with contact details"

    try:
        await send_email(to=notify_email, subject=subject, html=html)
        logger.info(f"[Notifier] Completion email sent to {notify_email} for job {job.get('id')}")
    except Exception as e:
        logger.error(f"[Notifier] Failed to send email: {e}")
