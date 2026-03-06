"""
Request authentication — re-exports from hephae_common.

Existing code does:
  from backend.lib.auth import verify_request, verify_api_key
This shim preserves that interface.
"""

from hephae_common.auth import verify_hmac_request as verify_request  # noqa: F401
from hephae_common.auth import verify_api_key  # noqa: F401
