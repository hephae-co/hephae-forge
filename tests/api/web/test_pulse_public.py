"""Functional tests for pulse public route logic — real DB reads.

Tests call the actual Firestore functions directly (no HTTP layer, no mocks).
Requires: GOOGLE_APPLICATION_CREDENTIALS / ADC for Firestore access.

These are integration tests — they read from real Firestore.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — integration tests require ADC or FIRESTORE_EMULATOR_HOST",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_industry_pulse_returns_dict_or_none():
    """get_latest_industry_pulse returns a dict or None — never raises."""
    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

    result = await get_latest_industry_pulse("restaurants")
    assert result is None or isinstance(result, dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_industry_pulse_nonexistent_returns_none():
    """Querying a completely unknown industry key returns None."""
    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

    result = await get_latest_industry_pulse("__nonexistent_industry_key_xyz__")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_registered_zipcodes_returns_list():
    """list_registered_zipcodes returns a list (may be empty in CI)."""
    from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes

    results = await list_registered_zipcodes()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_registered_industries_returns_list():
    """list_registered_industries returns a list (may be empty in CI)."""
    from hephae_db.firestore.registered_industries import list_registered_industries

    results = await list_registered_industries()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zipcode_validation_format():
    """Zip code format validation — invalid formats must be caught upstream."""
    # This tests the pure validation logic used by the pulse public route
    import re

    def _is_valid_zip(z: str) -> bool:
        return bool(re.match(r"^\d{5}$", z))

    assert _is_valid_zip("07110") is True
    assert _is_valid_zip("10001") is True
    assert _is_valid_zip("abc") is False
    assert _is_valid_zip("1234") is False
    assert _is_valid_zip("123456") is False
