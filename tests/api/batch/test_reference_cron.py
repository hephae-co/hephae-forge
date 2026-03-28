"""Functional tests for the reference harvester.

Tests the real harvest_references function — actual HTTP calls to Google News RSS
and authority sites. No mocks.

Requires: GEMINI_API_KEY (for title classification)
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — functional tests require a real Gemini API key",
)


@pytest.mark.functional
@pytest.mark.asyncio
async def test_harvest_references_returns_list():
    """harvest_references returns a list (may be empty if network unavailable)."""
    from hephae_agents.research.reference_harvester import harvest_references

    # Use a single topic to keep test fast
    results = await harvest_references(
        topics=["restaurant_food_cost"],
        week_of="test-week",
    )

    assert isinstance(results, list), "harvest_references must return a list"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_harvest_references_result_shape():
    """Each reference has required fields: id, url, title, source, relevance_score."""
    from hephae_agents.research.reference_harvester import harvest_references

    results = await harvest_references(
        topics=["restaurant_food_cost"],
        week_of="test-week",
    )

    for ref in results:
        assert isinstance(ref, dict)
        assert "id" in ref, "Reference must have an id"
        assert "url" in ref, "Reference must have a url"
        assert "title" in ref, "Reference must have a title"
        assert "source" in ref, "Reference must have a source"
        assert "relevance_score" in ref, "Reference must have relevance_score"
        score = ref["relevance_score"]
        assert 0.0 <= score <= 1.0, f"relevance_score {score} out of range [0, 1]"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_harvest_references_deduplication():
    """Running harvest twice with existing hashes skips already-seen URLs."""
    from hephae_agents.research.reference_harvester import harvest_references, _url_hash

    # First run
    results1 = await harvest_references(
        topics=["restaurant_food_cost"],
        week_of="test-week",
    )

    if not results1:
        pytest.skip("No references harvested (network unavailable)")

    # Second run with all existing hashes
    existing_hashes = {_url_hash(r["url"]) for r in results1}
    results2 = await harvest_references(
        topics=["restaurant_food_cost"],
        week_of="test-week",
        existing_url_hashes=existing_hashes,
    )

    # Overlap should be zero — all URLs were deduplicated
    new_urls = {r["url"] for r in results2}
    old_urls = {r["url"] for r in results1}
    overlap = new_urls & old_urls
    assert len(overlap) == 0, f"Deduplication failed: {len(overlap)} duplicate URLs found"
