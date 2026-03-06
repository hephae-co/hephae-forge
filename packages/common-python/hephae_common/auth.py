"""
Shared authentication utilities for hephae apps.

Web app uses: verify_hmac_request, verify_api_key (server-side verification)
Admin app uses: generate_hmac_headers, generate_api_key_headers (client-side signing)
"""

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import Header, HTTPException


# ── Secrets (from environment) ────────────────────────────────────────────

FORGE_API_SECRET = os.getenv("FORGE_API_SECRET", "")
FORGE_V1_API_KEY = os.getenv("FORGE_V1_API_KEY", "")


# ── Server-side verification (used by web app) ───────────────────────────


def verify_hmac_request(
    x_forge_timestamp: Optional[str] = Header(None),
    x_forge_signature: Optional[str] = Header(None),
):
    """Verify HMAC signature on incoming requests.

    Signature = HMAC-SHA256(secret, timestamp)
    Reject if timestamp is >5 minutes old.
    """
    if not FORGE_API_SECRET:
        return  # Skip auth in dev if no secret configured

    if not x_forge_timestamp or not x_forge_signature:
        raise HTTPException(status_code=401, detail="Missing auth headers")

    try:
        ts = int(x_forge_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    if abs(time.time() - ts) > 300:
        raise HTTPException(status_code=401, detail="Request expired")

    expected = hmac.new(
        FORGE_API_SECRET.encode(),
        x_forge_timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(x_forge_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")


def verify_api_key(
    x_api_key: Optional[str] = Header(None),
):
    """Validate API key for v1 headless routes."""
    if not FORGE_V1_API_KEY:
        return  # Skip in dev if no key configured

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not hmac.compare_digest(x_api_key, FORGE_V1_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Client-side signing (used by admin app) ───────────────────────────────


def generate_hmac_headers(secret: str = "") -> dict[str, str]:
    """Generate HMAC auth headers for calling forge API endpoints.

    Returns empty dict if secret is not provided (dev mode).
    """
    secret = secret or FORGE_API_SECRET
    if not secret:
        return {}

    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "x-forge-timestamp": timestamp,
        "x-forge-signature": signature,
    }


def generate_api_key_headers(api_key: str = "") -> dict[str, str]:
    """Generate API key header for v1 headless routes.

    Returns empty dict if key is not provided (dev mode).
    """
    key = api_key or FORGE_V1_API_KEY
    if not key:
        return {}

    return {"x-api-key": key}
