"""Functional tests for registered_industries Firestore module.

Tests call the real Firestore functions. They require ADC or
FIRESTORE_EMULATOR_HOST to be configured.

These are integration tests — they read/write real Firestore.
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
async def test_list_registered_industries_returns_list():
    """list_registered_industries always returns a list."""
    from hephae_db.firestore.registered_industries import list_registered_industries

    results = await list_registered_industries()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_registered_industries_with_status_filter():
    """list_registered_industries with status='active' returns a list."""
    from hephae_db.firestore.registered_industries import list_registered_industries

    results = await list_registered_industries(status="active")
    assert isinstance(results, list)
    for r in results:
        assert r.get("status") == "active"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_registered_industry_returns_dict_or_none():
    """get_registered_industry returns a dict or None — never raises."""
    from hephae_db.firestore.registered_industries import get_registered_industry

    result = await get_registered_industry("__nonexistent_industry_key_xyz__")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registered_industry_document_shape():
    """Active industries have required fields: industryKey, displayName, status."""
    from hephae_db.firestore.registered_industries import list_registered_industries

    results = await list_registered_industries()
    for industry in results:
        assert "industryKey" in industry, "Must have industryKey"
        assert "displayName" in industry, "Must have displayName"
        assert "status" in industry, "Must have status"
        assert isinstance(industry["industryKey"], str)
        assert len(industry["industryKey"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_industry_key_is_lowercase():
    """All registered industry keys should be lowercase."""
    from hephae_db.firestore.registered_industries import list_registered_industries

    results = await list_registered_industries()
    for industry in results:
        key = industry.get("industryKey", "")
        assert key == key.lower(), f"industryKey '{key}' is not lowercase"
