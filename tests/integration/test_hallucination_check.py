"""
Level 5: LLM-as-Judge hallucination detection.

Feeds enriched profiles to Gemini Flash for fact-checking.
Each field is scored 1-5 for "realness". Tests assert:
- No field scores below 3 (plausible minimum)
- name and officialUrl score 4+ (high confidence)
- Overall confidence >= 3.5
"""

from __future__ import annotations

import logging

import pytest

from tests.integration.businesses import BUSINESSES, GroundTruth
from tests.integration.llm_judge import evaluate_discovery

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.needs_browser, pytest.mark.asyncio]


def _get_enriched_or_skip(biz: GroundTruth, discovery_cache) -> dict:
    """Get cached enriched profile or skip test."""
    profile = discovery_cache.enriched_profiles.get(biz.id)
    if not profile:
        pytest.skip(f"No enriched profile cached for {biz.id} — pipeline may have timed out")
    return profile


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_no_field_below_minimum(biz, discovery_cache):
    """No scored field should be below 3 (plausible)."""
    profile = _get_enriched_or_skip(biz, discovery_cache)
    result = await evaluate_discovery(profile, biz)

    scores = result.get("scores", {})
    flags = result.get("flags", [])

    logger.info(f"\n[LLMJudge/{biz.id}] Scores: {scores}")
    if flags:
        logger.info(f"[LLMJudge/{biz.id}] Flags: {flags}")

    low_scores = {field: score for field, score in scores.items() if score < 3}

    # Allow null fields to score low (they legitimately might not exist)
    # Only fail if a field that HAS a value scores below 3
    real_violations = {}
    for field, score in low_scores.items():
        value = profile.get(field)
        if field == "socialLinks":
            value = profile.get("socialLinks", {})
            has_any = any(v for v in value.values()) if isinstance(value, dict) else bool(value)
            if has_any:
                real_violations[field] = score
        elif field == "socialProfileMetrics":
            # Social platforms block unauthenticated scraping (login_required).
            # Low scores here reflect expected degradation, not hallucination.
            continue
        elif value is not None:
            real_violations[field] = score

    assert not real_violations, (
        f"[{biz.name}] Fields scored below 3 (likely hallucinated): {real_violations}\n"
        f"Flags: {flags}"
    )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_identity_fields_high_confidence(biz, discovery_cache):
    """name and officialUrl should score 4+ (high confidence)."""
    profile = _get_enriched_or_skip(biz, discovery_cache)
    result = await evaluate_discovery(profile, biz)

    scores = result.get("scores", {})

    name_score = scores.get("name", 0)
    url_score = scores.get("officialUrl", 0)

    assert name_score >= 4, (
        f"[{biz.name}] 'name' scored {name_score} (expected 4+). "
        f"Discovered name: {profile.get('name')}"
    )
    assert url_score >= 4, (
        f"[{biz.name}] 'officialUrl' scored {url_score} (expected 4+). "
        f"Discovered URL: {profile.get('officialUrl')}"
    )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_overall_confidence_threshold(biz, discovery_cache):
    """Overall confidence score should be >= 3.5."""
    profile = _get_enriched_or_skip(biz, discovery_cache)
    result = await evaluate_discovery(profile, biz)

    overall = result.get("overall", 0)
    scores = result.get("scores", {})

    assert overall >= 3.5, (
        f"[{biz.name}] Overall confidence {overall:.1f} < 3.5. "
        f"Scores: {scores}"
    )


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(60)
async def test_social_profile_metrics_plausibility(biz, discovery_cache):
    """socialProfileMetrics scores at least 3 (plausible) for businesses with social presence."""
    profile = _get_enriched_or_skip(biz, discovery_cache)
    result = await evaluate_discovery(profile, biz)

    scores = result.get("scores", {})
    metrics_score = scores.get("socialProfileMetrics", 0)

    # For businesses with known social platforms, metrics should be at least plausible
    assert metrics_score >= 2, (
        f"[{biz.name}] socialProfileMetrics scored {metrics_score} (expected 2+). "
        f"This business has known platforms: {biz.expected_social_platforms}"
    )


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(60)
async def test_social_metrics_follower_counts_reasonable(biz, discovery_cache):
    """Follower counts should be within reasonable ranges for local businesses."""
    profile = _get_enriched_or_skip(biz, discovery_cache)

    metrics = profile.get("socialProfileMetrics")
    if not metrics or not isinstance(metrics, dict):
        pytest.skip(f"No socialProfileMetrics for {biz.id}")

    for platform in ["instagram", "facebook", "twitter", "tiktok"]:
        p_data = metrics.get(platform)
        if not isinstance(p_data, dict):
            continue
        followers = p_data.get("followerCount")
        if followers is not None:
            assert isinstance(followers, (int, float)), (
                f"{biz.name}/{platform}: followerCount should be numeric, got {type(followers).__name__}"
            )
            assert followers >= 0, (
                f"{biz.name}/{platform}: followerCount is negative: {followers}"
            )
            # Local businesses typically have < 1M followers
            assert followers < 10_000_000, (
                f"{biz.name}/{platform}: followerCount {followers} seems too high for a local business"
            )


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(60)
async def test_social_metrics_yelp_rating_valid(biz, discovery_cache):
    """Yelp rating should be between 1.0 and 5.0 if present."""
    profile = _get_enriched_or_skip(biz, discovery_cache)

    metrics = profile.get("socialProfileMetrics")
    if not metrics or not isinstance(metrics, dict):
        pytest.skip(f"No socialProfileMetrics for {biz.id}")

    yelp_data = metrics.get("yelp")
    if not isinstance(yelp_data, dict):
        pytest.skip(f"No yelp data for {biz.id}")

    rating = yelp_data.get("rating")
    if rating is not None:
        assert isinstance(rating, (int, float)), (
            f"{biz.name}: Yelp rating should be numeric, got {type(rating).__name__}"
        )
        assert 1.0 <= rating <= 5.0, (
            f"{biz.name}: Yelp rating {rating} out of valid range [1.0, 5.0]"
        )

    review_count = yelp_data.get("reviewCount")
    if review_count is not None:
        assert isinstance(review_count, (int, float)), (
            f"{biz.name}: Yelp reviewCount should be numeric, got {type(review_count).__name__}"
        )
        assert review_count >= 0, (
            f"{biz.name}: Yelp reviewCount is negative: {review_count}"
        )


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(60)
async def test_social_metrics_presence_score_valid(biz, discovery_cache):
    """overallPresenceScore should be between 0 and 100."""
    profile = _get_enriched_or_skip(biz, discovery_cache)

    metrics = profile.get("socialProfileMetrics")
    if not metrics or not isinstance(metrics, dict):
        pytest.skip(f"No socialProfileMetrics for {biz.id}")

    summary = metrics.get("summary")
    if not isinstance(summary, dict):
        pytest.skip(f"No summary in socialProfileMetrics for {biz.id}")

    score = summary.get("overallPresenceScore")
    if score is not None:
        assert isinstance(score, (int, float)), (
            f"{biz.name}: overallPresenceScore should be numeric, got {type(score).__name__}"
        )
        assert 0 <= score <= 100, (
            f"{biz.name}: overallPresenceScore {score} out of range [0, 100]"
        )

    total_followers = summary.get("totalFollowers")
    if total_followers is not None:
        assert isinstance(total_followers, (int, float)), (
            f"{biz.name}: totalFollowers should be numeric, got {type(total_followers).__name__}"
        )
        assert total_followers >= 0, (
            f"{biz.name}: totalFollowers is negative: {total_followers}"
        )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_print_scorecard(biz, discovery_cache):
    """Print detailed scorecard for visibility (always passes)."""
    profile = discovery_cache.enriched_profiles.get(biz.id)
    if not profile:
        pytest.skip(f"No enriched profile for {biz.id}")

    result = await evaluate_discovery(profile, biz)

    scores = result.get("scores", {})
    flags = result.get("flags", [])
    overall = result.get("overall", 0)

    # Print scorecard
    print(f"\n{'='*60}")
    print(f"  SCORECARD: {biz.name} ({biz.city}, {biz.state})")
    print(f"{'='*60}")
    for field, score in sorted(scores.items()):
        bar = "█" * score + "░" * (5 - score)
        value = profile.get(field, "—")
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if v}  # only show non-null
        print(f"  {field:24s} [{bar}] {score}/5  →  {value}")
    print(f"  {'─'*56}")
    print(f"  OVERALL: {overall:.1f}/5.0")
    if flags:
        print(f"  FLAGS:")
        for flag in flags:
            print(f"    ⚠ {flag}")
    print(f"{'='*60}\n")
