"""Functional tests for the business overview runner — real agent call, no mocks.

Requires: GEMINI_API_KEY
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — functional tests require a real Gemini API key",
)

_BOSPHORUS = {
    "name": "The Bosphorus",
    "address": "10 Main St, Nutley, NJ 07110",
    "officialUrl": "https://bosphorusnutley.com",
}


@pytest.mark.functional
@pytest.mark.asyncio
async def test_business_overview_returns_dict():
    """run_business_overview returns a non-empty dict."""
    from hephae_agents.business_overview.runner import run_business_overview

    result = await run_business_overview(_BOSPHORUS)

    assert isinstance(result, dict), "Overview must return a dict"
    assert result, "Result must be non-empty"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_business_overview_has_name_field():
    """Overview result should include the business name."""
    from hephae_agents.business_overview.runner import run_business_overview

    result = await run_business_overview(_BOSPHORUS)

    # Name should either come through directly or be in a nested field
    name = result.get("name") or result.get("businessName")
    if name:
        assert "Bosphorus" in name or "bosphorus" in name.lower()


@pytest.mark.functional
@pytest.mark.asyncio
async def test_business_overview_has_summary():
    """Overview result should include a summary string."""
    from hephae_agents.business_overview.runner import run_business_overview

    result = await run_business_overview(_BOSPHORUS)

    summary = result.get("summary") or result.get("description")
    if summary:
        assert isinstance(summary, str)
        assert len(summary) > 10, "Summary must be a substantive string"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_business_overview_raises_for_missing_name():
    """Missing business name should raise an error."""
    from hephae_agents.business_overview.runner import run_business_overview

    no_name = {**_BOSPHORUS, "name": None}
    with pytest.raises((ValueError, Exception)):
        await run_business_overview(no_name)
