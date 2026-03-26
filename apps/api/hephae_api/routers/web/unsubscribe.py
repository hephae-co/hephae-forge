"""GET /api/unsubscribe — one-click email unsubscribe handler."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Unsubscribed — Hephae</title>
  <style>
    body{margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;}
    .card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:48px 40px;max-width:460px;text-align:center;}
    h1{color:#e2e8f0;font-size:22px;margin:0 0 12px;}
    p{color:rgba(226,232,240,0.6);font-size:14px;line-height:1.6;margin:0;}
    a{color:#818cf8;text-decoration:none;}
  </style>
</head>
<body>
  <div class="card">
    <div style="font-size:32px;margin-bottom:16px;">✓</div>
    <h1>You're unsubscribed</h1>
    <p>You won't receive any more outreach emails from Hephae.<br/>
    <br/>If this was a mistake, email us at <a href="mailto:hello@hephae.co">hello@hephae.co</a>.</p>
  </div>
</body>
</html>"""

_INVALID_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Invalid Link — Hephae</title>
  <style>
    body{margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;}
    .card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:48px 40px;max-width:460px;text-align:center;}
    h1{color:#f87171;font-size:22px;margin:0 0 12px;}
    p{color:rgba(226,232,240,0.6);font-size:14px;line-height:1.6;margin:0;}
    a{color:#818cf8;text-decoration:none;}
  </style>
</head>
<body>
  <div class="card">
    <div style="font-size:32px;margin-bottom:16px;">✗</div>
    <h1>Invalid link</h1>
    <p>This unsubscribe link is invalid or has expired.<br/>
    Email <a href="mailto:hello@hephae.co">hello@hephae.co</a> and we'll remove you manually.</p>
  </div>
</body>
</html>"""


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    email: str = Query(...),
    token: str = Query(...),
):
    """One-click unsubscribe. Verifies HMAC token then saves to Firestore."""
    from hephae_db.firestore.email_unsubscribes import verify_unsubscribe_token, save_unsubscribe

    if not email or not token or not verify_unsubscribe_token(email, token):
        logger.warning(f"[Unsubscribe] Invalid token for {email!r}")
        return HTMLResponse(_INVALID_HTML, status_code=400)

    await save_unsubscribe(email)
    return HTMLResponse(_SUCCESS_HTML)
