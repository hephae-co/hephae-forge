"""
Auth helpers for calling hephae-forge API endpoints — re-exports from hephae_common.

Existing code does:
  from backend.lib.forge_auth import forge_hmac_headers, forge_api_key_headers
"""

from backend.config import settings
from hephae_common.auth import generate_hmac_headers, generate_api_key_headers


def forge_hmac_headers() -> dict[str, str]:
    """Generate HMAC auth headers using the app's configured secret."""
    return generate_hmac_headers(settings.FORGE_API_SECRET)


def forge_api_key_headers() -> dict[str, str]:
    """Generate API key header using the app's configured key."""
    return generate_api_key_headers(settings.FORGE_V1_API_KEY)
