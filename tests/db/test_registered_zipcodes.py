"""Functional tests for registered_zipcodes Firestore module.

Tests call the real Firestore functions. They require ADC or
FIRESTORE_EMULATOR_HOST to be configured.

These are integration tests — they read real Firestore.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — set GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_registered_zipcodes_returns_list():
    """list_registered_zipcodes always returns a list."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

    results = await list_registered_zipcodes()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_registered_zipcodes_with_status_filter():
    """list_registered_zipcodes with status='active' only returns active zips."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

    results = await list_registered_zipcodes(status="active")
    assert isinstance(results, list)
    for z in results:
        assert z.get("status") == "active", f"Expected active, got {z.get('status')}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_registered_zipcode_nonexistent_returns_none():
    """Querying a non-existent zip returns None."""
    from hephae_db.firestore.registered_zipcodes import get_registered_zipcode

    result = await get_registered_zipcode("00000")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registered_zipcode_document_shape():
    """Each registered zipcode document has required top-level fields."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

    results = await list_registered_zipcodes()
    for z in results:
        assert "zipCode" in z, "zipCode must be a top-level field (database rule)"
        assert isinstance(z["zipCode"], str)
        assert len(z["zipCode"]) == 5, f"zipCode '{z['zipCode']}' is not 5 digits"
        assert z["zipCode"].isdigit(), f"zipCode '{z['zipCode']}' is not numeric"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zipcode_has_city_and_state():
    """Registered zipcodes have city and state fields."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

    results = await list_registered_zipcodes()
    for z in results:
        assert "city" in z, "Must have city"
        assert "state" in z, "Must have state"


# ---------------------------------------------------------------------------
# Pure logic tests (no DB required)
# ---------------------------------------------------------------------------

class TestNextMondayHelper:
    def test_returns_future_monday(self):
        """_next_monday() always returns a future datetime on a Monday."""
        from hephae_db.firestore.registered_zipcodes import _next_monday

        result = _next_monday()
        assert result > datetime.utcnow()
        assert result.weekday() == 0  # Monday = 0

    def test_returns_11_utc(self):
        """_next_monday() returns 11:00 UTC (6am ET)."""
        from hephae_db.firestore.registered_zipcodes import _next_monday

        result = _next_monday()
        assert result.hour == 11
        assert result.minute == 0
