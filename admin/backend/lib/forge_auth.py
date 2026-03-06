"""Auth helpers for calling hephae-forge API endpoints."""

import hashlib
import hmac
import time

from backend.config import settings


def forge_hmac_headers() -> dict[str, str]:
    """Generate HMAC auth headers for forge capability/discover/analyze routes.

    Returns empty dict if FORGE_API_SECRET is not configured (dev mode).
    """
    secret = settings.FORGE_API_SECRET
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


def forge_api_key_headers() -> dict[str, str]:
    """Generate API key header for forge v1 headless routes.

    Returns empty dict if FORGE_V1_API_KEY is not configured (dev mode).
    """
    key = settings.FORGE_V1_API_KEY
    if not key:
        return {}

    return {"x-api-key": key}
