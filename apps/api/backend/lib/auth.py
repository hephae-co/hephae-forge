"""Request authentication for the unified API.

Re-exports auth functions from hephae_common for use in route dependencies.
"""

from hephae_common.auth import verify_hmac_request as verify_request  # noqa: F401
from hephae_common.auth import verify_api_key  # noqa: F401
