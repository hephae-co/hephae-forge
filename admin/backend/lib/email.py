"""Email sending via Resend API."""

from __future__ import annotations

import logging

import resend

from backend.config import settings

logger = logging.getLogger(__name__)


def _init_resend():
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured")
    resend.api_key = settings.RESEND_API_KEY


async def send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> str:
    """Send an email via Resend. Returns the email ID."""
    _init_resend()
    from_addr = settings.RESEND_FROM_EMAIL

    logger.info(f"[Resend] Sending email to {to}...")

    params: dict = {
        "from_": from_addr,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        params["html"] = html

    result = resend.Emails.send(params)
    email_id = result.get("id", "unknown") if isinstance(result, dict) else str(result)
    logger.info(f"[Resend] Email sent. ID: {email_id}")
    return email_id
