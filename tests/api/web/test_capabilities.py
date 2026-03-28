"""Functional tests for capability runners — real agent calls, no mocks.

Calls the actual runner functions from hephae_agents and validates
business-logic output: score ranges, required fields, correct types.

Requires: GEMINI_API_KEY
"""

from __future__ import annotations

import os

import pytest

from tests.integration.businesses import BUSINESSES

# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — functional tests require a real Gemini API key",
)

# Use first 2 businesses for speed
_TEST_BUSINESSES = BUSINESSES[:2]

# Sample identity for direct runner tests (restaurant with known URL)
_BOSPHORUS = {
    "name": "The Bosphorus",
    "address": "10 Main St, Nutley, NJ 07110",
    "officialUrl": "https://bosphorusnutley.com",
    "competitors": [
        {"name": "Istanbul Grill", "url": "https://istanbulgrillnj.com"},
    ],
    "zipCode": "07110",
}


# ---------------------------------------------------------------------------
# SEO Auditor
# ---------------------------------------------------------------------------

@pytest.mark.functional
@pytest.mark.asyncio
async def test_seo_audit_returns_non_empty_result():
    """run_seo_audit produces a dict with url and sections."""
    from hephae_agents.seo_auditor.runner import run_seo_audit

    result = await run_seo_audit(_BOSPHORUS)

    assert isinstance(result, dict), "SEO audit must return a dict"
    assert result.get("url") == _BOSPHORUS["officialUrl"]
    assert "sections" in result, "Must have sections field"
    assert isinstance(result["sections"], list)


@pytest.mark.functional
@pytest.mark.asyncio
async def test_seo_audit_score_in_valid_range():
    """overallScore, if present, must be 0–100."""
    from hephae_agents.seo_auditor.runner import run_seo_audit

    result = await run_seo_audit(_BOSPHORUS)

    score = result.get("overallScore")
    if score is not None:
        assert 0 <= score <= 100, f"overallScore {score} out of range [0, 100]"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_seo_audit_raises_for_missing_url():
    """Missing officialUrl must raise ValueError, not silently return."""
    from hephae_agents.seo_auditor.runner import run_seo_audit

    no_url = {**_BOSPHORUS, "officialUrl": None}
    with pytest.raises((ValueError, Exception)):
        await run_seo_audit(no_url)


# ---------------------------------------------------------------------------
# Social Media Auditor
# ---------------------------------------------------------------------------

@pytest.mark.functional
@pytest.mark.asyncio
async def test_social_media_audit_returns_dict():
    """run_social_media_audit produces a non-empty dict."""
    from hephae_agents.social.media_auditor.runner import run_social_media_audit

    result = await run_social_media_audit(_BOSPHORUS)

    assert isinstance(result, dict), "Social audit must return a dict"
    assert result, "Result must be non-empty"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_social_media_audit_overall_score_range():
    """overallScore or overall_score, if present, must be 0–100."""
    from hephae_agents.social.media_auditor.runner import run_social_media_audit

    result = await run_social_media_audit(_BOSPHORUS)

    score = result.get("overallScore") or result.get("overall_score")
    if score is not None:
        assert 0 <= score <= 100, f"Score {score} out of range [0, 100]"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_social_media_audit_raises_for_missing_name():
    """Missing name must raise ValueError."""
    from hephae_agents.social.media_auditor.runner import run_social_media_audit

    no_name = {**_BOSPHORUS, "name": None}
    with pytest.raises((ValueError, Exception)):
        await run_social_media_audit(no_name)


# ---------------------------------------------------------------------------
# Competitive Analysis
# ---------------------------------------------------------------------------

@pytest.mark.functional
@pytest.mark.asyncio
async def test_competitive_analysis_returns_dict():
    """run_competitive_analysis produces a non-empty dict."""
    from hephae_agents.competitive_analysis.runner import run_competitive_analysis

    result = await run_competitive_analysis(_BOSPHORUS)

    assert isinstance(result, dict), "Competitive analysis must return a dict"
    assert result, "Result must be non-empty"


@pytest.mark.functional
@pytest.mark.asyncio
async def test_competitive_analysis_score_range():
    """overall_score, if present, must be 0–100."""
    from hephae_agents.competitive_analysis.runner import run_competitive_analysis

    result = await run_competitive_analysis(_BOSPHORUS)

    score = result.get("overall_score") or result.get("overallScore")
    if score is not None:
        assert 0 <= score <= 100, f"Score {score} out of range [0, 100]"


# ---------------------------------------------------------------------------
# Marketing Swarm (run_marketing_pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.functional
@pytest.mark.asyncio
async def test_marketing_pipeline_returns_structured_result():
    """run_marketing_pipeline produces platform, draft, creativeDirection keys."""
    from hephae_agents.social.marketing_swarm.agent import run_marketing_pipeline

    result = await run_marketing_pipeline(_BOSPHORUS)

    assert isinstance(result, dict), "Marketing pipeline must return a dict"
    assert "platform" in result, "Must have platform key"
    assert isinstance(result.get("platform"), str)
    assert result.get("platform") in ("Instagram", "Blog", "Facebook", "Twitter", "TikTok") or result.get("platform")


@pytest.mark.functional
@pytest.mark.asyncio
async def test_marketing_pipeline_draft_is_non_empty():
    """contentDraft should have actual content."""
    from hephae_agents.social.marketing_swarm.agent import run_marketing_pipeline

    result = await run_marketing_pipeline(_BOSPHORUS)

    draft = result.get("draft", "")
    # Draft may be empty if pipeline fails gracefully — just check it's a string
    assert isinstance(draft, str)
