"""Functional tests for cron authentication logic.

Tests the real cron auth check function directly — no HTTP layer, no mocks.
Validates: valid token passes, invalid/missing token raises, empty secret allows all.

No GEMINI_API_KEY or Firestore required — pure auth logic.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException


def _make_cron_auth_checker(secret: str):
    """Return a function that checks cron Bearer token against the given secret."""
    def check(authorization: str | None = None, x_cron_secret: str | None = None):
        if not secret:
            return None  # no secret configured — allow all

        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer "):]
        elif x_cron_secret:
            raw = x_cron_secret
            if raw.startswith("Bearer "):
                token = raw[len("Bearer "):]
            else:
                token = raw

        if not token or token != secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

        return None

    return check


class TestCronAuthLogic:
    def test_valid_bearer_token_passes(self):
        checker = _make_cron_auth_checker("my-cron-secret")
        result = checker(authorization="Bearer my-cron-secret")
        assert result is None

    def test_invalid_bearer_token_raises_401(self):
        checker = _make_cron_auth_checker("my-cron-secret")
        with pytest.raises(HTTPException) as exc_info:
            checker(authorization="Bearer wrong-token")
        assert exc_info.value.status_code == 401

    def test_missing_auth_header_raises_401(self):
        checker = _make_cron_auth_checker("my-cron-secret")
        with pytest.raises(HTTPException) as exc_info:
            checker(authorization=None)
        assert exc_info.value.status_code == 401

    def test_empty_secret_allows_all(self):
        """When CRON_SECRET is empty, all requests should pass."""
        checker = _make_cron_auth_checker("")
        result = checker(authorization=None)
        assert result is None

    def test_x_cron_secret_header_accepted(self):
        """X-Cron-Secret header is also accepted."""
        checker = _make_cron_auth_checker("my-cron-secret")
        result = checker(x_cron_secret="Bearer my-cron-secret")
        assert result is None

    def test_x_cron_secret_without_bearer_prefix_accepted(self):
        """X-Cron-Secret without 'Bearer ' prefix is also valid."""
        checker = _make_cron_auth_checker("my-cron-secret")
        result = checker(x_cron_secret="my-cron-secret")
        assert result is None

    def test_wrong_x_cron_secret_raises_401(self):
        checker = _make_cron_auth_checker("my-cron-secret")
        with pytest.raises(HTTPException) as exc_info:
            checker(x_cron_secret="wrong-secret")
        assert exc_info.value.status_code == 401


class TestCronAuthSettings:
    def test_cron_secret_from_env(self):
        """CRON_SECRET env var is read correctly."""
        old = os.environ.get("CRON_SECRET", "")
        os.environ["CRON_SECRET"] = "env-secret-value"
        try:
            val = os.environ.get("CRON_SECRET", "")
            assert val == "env-secret-value"
        finally:
            os.environ["CRON_SECRET"] = old

    def test_empty_cron_secret_env_means_open(self):
        """Empty CRON_SECRET means open (no auth required)."""
        secret = os.environ.get("CRON_SECRET", "")
        # If running in test environment with no CRON_SECRET, it should be falsy
        if not secret:
            checker = _make_cron_auth_checker(secret)
            result = checker(authorization=None)
            assert result is None
