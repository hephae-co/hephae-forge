"""Functional tests for industry_pulse Firestore module.

Tests call the real Firestore functions. They require ADC or
FIRESTORE_EMULATOR_HOST to be configured.

These are integration tests — they read real Firestore.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — set GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_industry_pulse_nonexistent_returns_none():
    """Querying a non-existent industry+week returns None."""
    from hephae_db.firestore.industry_pulse import get_industry_pulse

    result = await get_industry_pulse("__nonexistent__", "9999-W99")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_industry_pulse_returns_dict_or_none():
    """get_latest_industry_pulse returns a dict or None — never raises."""
    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

    result = await get_latest_industry_pulse("restaurants")
    assert result is None or isinstance(result, dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_industry_pulse_shape():
    """When a pulse exists, it has required fields."""
    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

    result = await get_latest_industry_pulse("restaurants")
    if result is None:
        pytest.skip("No restaurants pulse in Firestore yet")

    assert "industryKey" in result
    assert "weekOf" in result
    assert result["industryKey"] == "restaurants"
    assert isinstance(result["weekOf"], str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_industry_pulses_returns_list():
    """list_industry_pulses always returns a list."""
    from hephae_db.firestore.industry_pulse import list_industry_pulses

    results = await list_industry_pulses()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_industry_pulses_filter_by_key():
    """Filtering by industry_key returns only matching pulses."""
    from hephae_db.firestore.industry_pulse import list_industry_pulses

    results = await list_industry_pulses(industry_key="restaurants")
    assert isinstance(results, list)
    for pulse in results:
        assert pulse.get("industryKey") == "restaurants"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_industry_pulses_limit():
    """list_industry_pulses respects the limit parameter."""
    from hephae_db.firestore.industry_pulse import list_industry_pulses

    results = await list_industry_pulses(limit=2)
    assert isinstance(results, list)
    assert len(results) <= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_industry_pulse_week_of_format():
    """weekOf field must match YYYY-Www format."""
    from hephae_db.firestore.industry_pulse import list_industry_pulses
    import re

    results = await list_industry_pulses(limit=5)
    for pulse in results:
        week_of = pulse.get("weekOf", "")
        assert re.match(r"^\d{4}-W\d{2}$", week_of), (
            f"weekOf '{week_of}' doesn't match YYYY-Www format"
        )
