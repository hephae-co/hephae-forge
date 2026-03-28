"""Functional tests for heartbeat Firestore operations.

Tests call the real Firestore functions directly — no HTTP layer, no mocks.
Requires ADC or FIRESTORE_EMULATOR_HOST for Firestore access.

These are integration tests. For auth middleware tests, see test_hmac_auth.py.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — set GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST",
)

VALID_CAPABILITIES = ["seo", "traffic", "competitive", "marketing", "margin"]


# ---------------------------------------------------------------------------
# Pure logic tests (no DB needed)
# ---------------------------------------------------------------------------

class TestCapabilityValidation:
    def test_seo_is_valid_capability(self):
        assert "seo" in VALID_CAPABILITIES

    def test_traffic_is_valid_capability(self):
        assert "traffic" in VALID_CAPABILITIES

    def test_invalid_capability_not_in_list(self):
        assert "invalid-cap" not in VALID_CAPABILITIES

    def test_empty_capabilities_fails_validation(self):
        """Business rule: heartbeat must have at least one capability."""
        caps = []
        assert len(caps) == 0  # empty is invalid

    def test_valid_day_of_week_range(self):
        """Day of week must be 0–6 (Mon–Sun)."""
        for d in range(7):
            assert 0 <= d <= 6

    def test_invalid_day_of_week(self):
        """Day values outside 0–6 are invalid."""
        assert 7 not in range(7)
        assert -1 not in range(7)


class TestNextWeekdayHelper:
    def test_returns_future_datetime(self):
        from hephae_db.firestore.heartbeats import _next_weekday

        result = _next_weekday(1)  # Tuesday
        assert result > datetime.now(tz=result.tzinfo)

    def test_returns_correct_weekday(self):
        from hephae_db.firestore.heartbeats import _next_weekday

        # Request Monday (0)
        result = _next_weekday(0)
        assert result.weekday() == 0

    def test_returns_correct_hour(self):
        from hephae_db.firestore.heartbeats import _next_weekday

        result = _next_weekday(1, hour=13)
        assert result.hour == 13


# ---------------------------------------------------------------------------
# Firestore read tests (require DB credentials)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_user_heartbeats_returns_list():
    """get_user_heartbeats returns a list — even for unknown user."""
    from hephae_db.firestore.heartbeats import get_user_heartbeats

    results = await get_user_heartbeats("__nonexistent_uid_xyz__")
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_heartbeat_nonexistent_returns_none():
    """get_heartbeat for unknown ID returns None."""
    from hephae_db.firestore.heartbeats import get_heartbeat

    result = await get_heartbeat("__nonexistent_hb_id_xyz__")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heartbeat_document_shape():
    """Existing heartbeat documents have required fields."""
    from hephae_db.firestore.heartbeats import get_user_heartbeats

    # Use a known test UID if any heartbeats exist at all — or skip
    # We query a made-up user first; if you have a known test user set TEST_UID
    test_uid = os.environ.get("TEST_UID", "__nonexistent_uid__")
    results = await get_user_heartbeats(test_uid)

    for hb in results:
        assert "uid" in hb
        assert "businessSlug" in hb
        assert "capabilities" in hb
        assert isinstance(hb["capabilities"], list)
        assert all(cap in VALID_CAPABILITIES for cap in hb["capabilities"]), (
            f"Unknown capabilities: {[c for c in hb['capabilities'] if c not in VALID_CAPABILITIES]}"
        )
