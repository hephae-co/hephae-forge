"""Unit tests for hephae_common.auth — token verification, admin checks, optional auth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Tests: verify_firebase_token
# ---------------------------------------------------------------------------

class TestVerifyFirebaseToken:
    def test_rejects_missing_token(self):
        from hephae_common.auth import verify_firebase_token

        with pytest.raises(HTTPException) as exc_info:
            verify_firebase_token(x_firebase_token=None)

        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    def test_rejects_empty_token(self):
        from hephae_common.auth import verify_firebase_token

        with pytest.raises(HTTPException) as exc_info:
            verify_firebase_token(x_firebase_token="")

        assert exc_info.value.status_code == 401

    def test_accepts_valid_token(self):
        decoded = {
            "uid": "user-123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://photo.url/pic.jpg",
        }

        with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
            from hephae_common.auth import verify_firebase_token

            result = verify_firebase_token(x_firebase_token="valid-token-abc")

        assert result["uid"] == "user-123"
        assert result["email"] == "test@example.com"
        assert result["name"] == "Test User"
        assert result["picture"] == "https://photo.url/pic.jpg"

    def test_rejects_invalid_token(self):
        with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Token expired")):
            from hephae_common.auth import verify_firebase_token

            with pytest.raises(HTTPException) as exc_info:
                verify_firebase_token(x_firebase_token="expired-token")

            assert exc_info.value.status_code == 401
            assert "Invalid" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Tests: verify_admin_request
# ---------------------------------------------------------------------------

class TestVerifyAdminRequest:
    def test_rejects_non_allowlisted_email(self):
        decoded = {"uid": "user-456", "email": "hacker@evil.com", "name": "Hacker"}

        with (
            patch("firebase_admin.auth.verify_id_token", return_value=decoded),
            patch("hephae_common.auth.ADMIN_EMAIL_ALLOWLIST", ["admin@hephae.co"]),
        ):
            from hephae_common.auth import verify_admin_request

            with pytest.raises(HTTPException) as exc_info:
                verify_admin_request(x_firebase_token="valid-token", x_api_key=None)

            assert exc_info.value.status_code == 403
            assert "Not authorized" in exc_info.value.detail

    def test_allows_allowlisted_email(self):
        decoded = {"uid": "admin-1", "email": "admin@hephae.co", "name": "Admin"}

        with (
            patch("firebase_admin.auth.verify_id_token", return_value=decoded),
            patch("hephae_common.auth.ADMIN_EMAIL_ALLOWLIST", ["admin@hephae.co"]),
        ):
            from hephae_common.auth import verify_admin_request

            result = verify_admin_request(x_firebase_token="admin-token", x_api_key=None)

        assert result["uid"] == "admin-1"
        assert result["email"] == "admin@hephae.co"

    def test_allows_all_when_no_allowlist(self):
        decoded = {"uid": "user-789", "email": "anyone@example.com", "name": "Anyone"}

        with (
            patch("firebase_admin.auth.verify_id_token", return_value=decoded),
            patch("hephae_common.auth.ADMIN_EMAIL_ALLOWLIST", []),
        ):
            from hephae_common.auth import verify_admin_request

            result = verify_admin_request(x_firebase_token="token", x_api_key=None)

        assert result["uid"] == "user-789"


# ---------------------------------------------------------------------------
# Tests: optional_firebase_user
# ---------------------------------------------------------------------------

class TestOptionalFirebaseUser:
    def test_returns_none_when_no_token(self):
        from hephae_common.auth import optional_firebase_user

        result = optional_firebase_user(x_firebase_token=None)
        assert result is None

    def test_returns_none_on_invalid_token(self):
        with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("bad")):
            from hephae_common.auth import optional_firebase_user

            result = optional_firebase_user(x_firebase_token="bad-token")

        assert result is None

    def test_returns_user_on_valid_token(self):
        decoded = {"uid": "user-opt", "email": "opt@test.com"}

        with patch("firebase_admin.auth.verify_id_token", return_value=decoded):
            from hephae_common.auth import optional_firebase_user

            result = optional_firebase_user(x_firebase_token="good-token")

        assert result["uid"] == "user-opt"
        assert result["email"] == "opt@test.com"
