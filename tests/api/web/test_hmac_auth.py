"""Unit tests for HMAC auth (verify_hmac_request / verify_request).

Tests verify_hmac_request directly — valid sig passes, invalid raises 401,
missing headers raise 401, expired timestamp raises 401.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException


TEST_SECRET = "test-forge-secret"


def _make_signature(secret: str, timestamp: str) -> str:
    return hmac.new(
        secret.encode(),
        timestamp.encode(),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Tests: verify_hmac_request
# ---------------------------------------------------------------------------

class TestVerifyHmacRequest:
    def test_valid_signature_passes(self):
        """Fresh signature with correct secret should not raise."""
        timestamp = str(int(time.time()))
        sig = _make_signature(TEST_SECRET, timestamp)

        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            # Should not raise
            result = verify_hmac_request(
                x_forge_timestamp=timestamp,
                x_forge_signature=sig,
            )
            assert result is None  # Returns None on success

    def test_invalid_signature_raises_401(self):
        """Wrong signature → 401."""
        timestamp = str(int(time.time()))
        wrong_sig = "deadbeef" * 8  # wrong hex

        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            with pytest.raises(HTTPException) as exc_info:
                verify_hmac_request(
                    x_forge_timestamp=timestamp,
                    x_forge_signature=wrong_sig,
                )
            assert exc_info.value.status_code == 401

    def test_missing_signature_header_raises_401(self):
        """No signature header → 401."""
        timestamp = str(int(time.time()))

        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            with pytest.raises(HTTPException) as exc_info:
                verify_hmac_request(
                    x_forge_timestamp=timestamp,
                    x_forge_signature=None,
                )
            assert exc_info.value.status_code == 401

    def test_missing_timestamp_header_raises_401(self):
        """No timestamp header → 401."""
        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            with pytest.raises(HTTPException) as exc_info:
                verify_hmac_request(
                    x_forge_timestamp=None,
                    x_forge_signature="some-sig",
                )
            assert exc_info.value.status_code == 401

    def test_expired_timestamp_raises_401(self):
        """Timestamp older than 5 minutes (300 seconds) → 401."""
        old_ts = str(int(time.time()) - 400)  # 400 seconds ago
        sig = _make_signature(TEST_SECRET, old_ts)

        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            with pytest.raises(HTTPException) as exc_info:
                verify_hmac_request(
                    x_forge_timestamp=old_ts,
                    x_forge_signature=sig,
                )
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

    def test_no_secret_configured_skips_auth(self):
        """When FORGE_API_SECRET is empty, all requests pass."""
        with patch.dict(os.environ, {"FORGE_API_SECRET": ""}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            # No headers provided, but no secret → should not raise
            result = verify_hmac_request(
                x_forge_timestamp=None,
                x_forge_signature=None,
            )
            assert result is None

    def test_invalid_timestamp_format_raises_401(self):
        """Non-numeric timestamp → 401."""
        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import verify_hmac_request

            with pytest.raises(HTTPException) as exc_info:
                verify_hmac_request(
                    x_forge_timestamp="not-a-number",
                    x_forge_signature="some-sig",
                )
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Tests: generate_hmac_headers (round-trip)
# ---------------------------------------------------------------------------

class TestGenerateHmacHeaders:
    def test_generate_and_verify_round_trip(self):
        """Headers generated by generate_hmac_headers should pass verify."""
        with patch.dict(os.environ, {"FORGE_API_SECRET": TEST_SECRET}):
            import importlib
            import hephae_common.auth
            importlib.reload(hephae_common.auth)

            from hephae_common.auth import generate_hmac_headers, verify_hmac_request

            headers = generate_hmac_headers(TEST_SECRET)
            assert "x-forge-timestamp" in headers
            assert "x-forge-signature" in headers

            # Should not raise
            verify_hmac_request(
                x_forge_timestamp=headers["x-forge-timestamp"],
                x_forge_signature=headers["x-forge-signature"],
            )

    def test_returns_empty_dict_when_no_secret(self):
        from hephae_common.auth import generate_hmac_headers

        headers = generate_hmac_headers("")
        assert headers == {}
