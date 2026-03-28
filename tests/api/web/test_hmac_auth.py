"""Real unit tests for HMAC auth — calls verify_hmac_request directly.

These tests do NOT use mocks. They call the real auth function with real
HMAC signatures and validate the correct behavior (pass/reject).

No GEMINI_API_KEY required — pure cryptographic logic.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

import pytest
from fastapi import HTTPException


TEST_SECRET = "test-forge-secret-12345"


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
        """Fresh HMAC signature with correct secret must not raise."""
        timestamp = str(int(time.time()))
        sig = _make_signature(TEST_SECRET, timestamp)

        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            result = auth_module.verify_hmac_request(
                x_forge_timestamp=timestamp,
                x_forge_signature=sig,
            )
            assert result is None  # returns None on success
        finally:
            os.environ["FORGE_API_SECRET"] = old
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

    def test_invalid_signature_raises_401(self):
        """Wrong signature must raise 401."""
        timestamp = str(int(time.time()))
        wrong_sig = "deadbeef" * 8

        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_hmac_request(
                    x_forge_timestamp=timestamp,
                    x_forge_signature=wrong_sig,
                )
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_missing_signature_header_raises_401(self):
        """No signature header must raise 401."""
        timestamp = str(int(time.time()))

        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_hmac_request(
                    x_forge_timestamp=timestamp,
                    x_forge_signature=None,
                )
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_missing_timestamp_header_raises_401(self):
        """No timestamp header must raise 401."""
        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_hmac_request(
                    x_forge_timestamp=None,
                    x_forge_signature="some-sig",
                )
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_expired_timestamp_raises_401(self):
        """Timestamp older than 300 seconds must raise 401 with 'expired' detail."""
        old_ts = str(int(time.time()) - 400)
        sig = _make_signature(TEST_SECRET, old_ts)

        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_hmac_request(
                    x_forge_timestamp=old_ts,
                    x_forge_signature=sig,
                )
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_no_secret_configured_skips_auth(self):
        """When FORGE_API_SECRET is empty, requests pass without headers."""
        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = ""
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            result = auth_module.verify_hmac_request(
                x_forge_timestamp=None,
                x_forge_signature=None,
            )
            assert result is None
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_invalid_timestamp_format_raises_401(self):
        """Non-numeric timestamp must raise 401."""
        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)
            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_hmac_request(
                    x_forge_timestamp="not-a-number",
                    x_forge_signature="some-sig",
                )
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)


# ---------------------------------------------------------------------------
# Tests: generate_hmac_headers (round-trip)
# ---------------------------------------------------------------------------

class TestGenerateHmacHeaders:
    def test_generate_and_verify_round_trip(self):
        """Headers from generate_hmac_headers must pass verify_hmac_request."""
        old = os.environ.get("FORGE_API_SECRET", "")
        os.environ["FORGE_API_SECRET"] = TEST_SECRET
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

            headers = auth_module.generate_hmac_headers(TEST_SECRET)
            assert "x-forge-timestamp" in headers
            assert "x-forge-signature" in headers

            # Round-trip: generated headers must verify cleanly
            result = auth_module.verify_hmac_request(
                x_forge_timestamp=headers["x-forge-timestamp"],
                x_forge_signature=headers["x-forge-signature"],
            )
            assert result is None
        finally:
            os.environ["FORGE_API_SECRET"] = old
            importlib.reload(auth_module)

    def test_returns_empty_dict_when_no_secret(self):
        """generate_hmac_headers with empty secret returns {}."""
        from hephae_common.auth import generate_hmac_headers
        headers = generate_hmac_headers("")
        assert headers == {}
