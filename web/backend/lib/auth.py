"""Request authentication for capability and v1 routes."""

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import Header, HTTPException

# Shared secret for HMAC signing (Next.js proxy <-> FastAPI)
FORGE_API_SECRET = os.getenv("FORGE_API_SECRET", "")

# API key for v1 headless routes (admin app)
FORGE_V1_API_KEY = os.getenv("FORGE_V1_API_KEY", "")


def verify_request(
    x_forge_timestamp: Optional[str] = Header(None),
    x_forge_signature: Optional[str] = Header(None),
):
    """Verify HMAC signature on incoming requests from the Next.js proxy.

    Signature = HMAC-SHA256(secret, timestamp)
    Reject if timestamp is >5 minutes old.
    """
    if not FORGE_API_SECRET:
        return  # Skip auth in dev if no secret configured

    if not x_forge_timestamp or not x_forge_signature:
        raise HTTPException(status_code=401, detail="Missing auth headers")

    # Check timestamp freshness (5 min window)
    try:
        ts = int(x_forge_timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    if abs(time.time() - ts) > 300:
        raise HTTPException(status_code=401, detail="Request expired")

    # Verify signature
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
    """Validate API key for v1 headless routes (admin/programmatic access)."""
    if not FORGE_V1_API_KEY:
        return  # Skip in dev if no key configured

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not hmac.compare_digest(x_api_key, FORGE_V1_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
