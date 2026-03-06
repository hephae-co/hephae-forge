"""
Email sending via Resend — mirrors src/lib/email.ts.
"""

from __future__ import annotations

import html
import logging
import os
from typing import Optional

import resend

logger = logging.getLogger(__name__)

EmailReportType = str  # 'profile' | 'margin' | 'traffic' | 'seo' | 'competitive'

REPORT_META: dict[str, dict[str, str]] = {
    "profile": {
        "label": "Business Profile",
        "accent": "#818cf8",
        "tagline": "Your digital identity, decoded.",
    },
    "margin": {
        "label": "Margin Surgery Report",
        "accent": "#f87171",
        "tagline": "We found the invisible bleed in your margins.",
    },
    "traffic": {
        "label": "Foot Traffic Forecast",
        "accent": "#4ade80",
        "tagline": "Your 3-day traffic crystal ball is ready.",
    },
    "seo": {
        "label": "SEO Deep Audit",
        "accent": "#a78bfa",
        "tagline": "Your search visibility, dissected.",
    },
    "competitive": {
        "label": "Competitive Strategy",
        "accent": "#fb923c",
        "tagline": "Know thy rivals. Then outmaneuver them.",
    },
}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def build_report_email_html(
    business_name: str,
    report_type: EmailReportType,
    report_url: str,
    summary: str,
) -> str:
    """Build the HTML email template for a report notification."""
    meta = REPORT_META.get(report_type, REPORT_META["profile"])
    accent = meta["accent"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(meta['label'])} - {_esc(business_name)}</title>
</head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <tr>
            <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:32px 40px;text-align:center;">
              <div style="font-size:24px;font-weight:800;color:#ffffff;margin-bottom:4px;">Hephae</div>
              <div style="font-size:13px;color:rgba(255,255,255,0.7);">Surgical Intelligence for Local Businesses</div>
            </td>
          </tr>
          <tr>
            <td style="background:rgba(255,255,255,0.03);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:40px;">
              <div style="text-align:center;margin-bottom:24px;">
                <span style="display:inline-block;background:{accent}22;color:{accent};border:1px solid {accent}44;padding:6px 16px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">{_esc(meta['label'])}</span>
              </div>
              <div style="text-align:center;margin-bottom:8px;">
                <span style="font-size:22px;font-weight:800;color:#e2e8f0;">{_esc(business_name)}</span>
              </div>
              <div style="text-align:center;margin-bottom:28px;">
                <span style="font-size:14px;color:{accent};font-style:italic;">{_esc(meta['tagline'])}</span>
              </div>
              <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 24px;margin-bottom:32px;">
                <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:rgba(226,232,240,0.5);margin-bottom:10px;">Key Findings</div>
                <div style="font-size:15px;color:#e2e8f0;line-height:1.65;">{_esc(summary)}</div>
              </div>
              <div style="text-align:center;margin-bottom:16px;">
                <a href="{_esc(report_url)}" target="_blank" style="display:inline-block;background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#ffffff;font-weight:700;font-size:16px;padding:14px 40px;border-radius:12px;text-decoration:none;">
                  View Full Report &rarr;
                </a>
              </div>
              <div style="text-align:center;font-size:12px;color:rgba(226,232,240,0.35);margin-top:8px;">
                This report is hosted securely and accessible anytime.
              </div>
            </td>
          </tr>
          <tr>
            <td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 16px 16px;padding:24px 40px;text-align:center;">
              <div style="font-size:12px;color:rgba(226,232,240,0.3);line-height:1.6;">
                Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a><br/>
                Surgical intelligence, delivered.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_report_email(
    to: str,
    business_name: str,
    report_type: EmailReportType,
    report_url: str,
    summary: str,
) -> dict:
    """Send a report email via Resend. Returns {success, id?, error?}."""
    try:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY is not set")

        resend.api_key = api_key
        meta = REPORT_META.get(report_type, REPORT_META["profile"])

        email_html = build_report_email_html(business_name, report_type, report_url, summary)

        result = resend.Emails.send({
            "from": "Chris from Hephae <chris@hephae.co>",
            "to": [to],
            "subject": f"{meta['label']} Ready: {business_name}",
            "html": email_html,
        })

        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        logger.info(f"[Email] Sent {report_type} report email to {to} (id: {email_id})")
        return {"success": True, "id": email_id}
    except Exception as err:
        message = str(err)
        logger.error(f"[Email] Failed to send report email: {message}")
        return {"success": False, "error": message}
