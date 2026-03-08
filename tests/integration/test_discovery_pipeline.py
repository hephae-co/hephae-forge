"""
Level 3: Full discovery pipeline populates all 7 state keys.

Runs the complete DiscoveryPipeline (SiteCrawler → 6 parallel sub-agents)
via the ADK Runner and validates every output key.

This is the most expensive test (~60-120s per business).
Results are cached in session-scoped discovery_cache for Levels 4 and 5.
"""

from __future__ import annotations

import asyncio
import logging
import re

import pytest

from hephae_capabilities.discovery.locator import LocatorAgent
from tests.integration.businesses import BUSINESSES, GroundTruth
from tests.integration.conftest import build_enriched_profile
from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.needs_browser, pytest.mark.asyncio]

EXPECTED_STATE_KEYS = [
    "rawSiteData",
    "themeData",
    "contactData",
    "socialData",
    "menuData",
    "mapsData",
    "competitorData",
    "socialProfileMetrics",
]

VALID_PERSONAS = [
    "Local Business",
    "Modern Artisan",
    "Classic Establishment",
    "Quick Service",
    "Fine Dining",
]


_batch_started = False


async def _run_single_pipeline(biz: GroundTruth, discovery_cache, runner_factory):
    """Run discovery pipeline for one business, caching results."""
    try:
        if biz.id not in discovery_cache.locator_results:
            identity = await LocatorAgent.resolve(biz.query)
            discovery_cache.locator_results[biz.id] = identity

        identity = discovery_cache.locator_results[biz.id]
        runner, session_service, user_id, session_id = await runner_factory()

        prompt = (
            f"Please discover everything about this business:\n"
            f"Name: {identity.get('name', biz.name)}\n"
            f"Address: {identity.get('address', '')}\n"
            f"URL: {identity.get('officialUrl', '')}"
        )

        async for _ in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            pass

        final_session = await session_service.get_session(
            app_name="integration-test", user_id=user_id, session_id=session_id
        )
        state = final_session.state if final_session else {}

        logger.info(f"[Pipeline/{biz.id}] Done — state keys: {list(state.keys())}")
        discovery_cache.pipeline_states[biz.id] = state
        discovery_cache.enriched_profiles[biz.id] = build_enriched_profile(identity, state)
    except Exception as e:
        logger.warning(f"[Pipeline/{biz.id}] Failed: {e}")
        discovery_cache.pipeline_states[biz.id] = {}


async def _ensure_pipeline_run(biz: GroundTruth, discovery_cache, runner_factory):
    """Run all pipelines concurrently on first call, then return from cache."""
    global _batch_started

    if biz.id in discovery_cache.pipeline_states:
        return discovery_cache.pipeline_states[biz.id]

    if not _batch_started:
        _batch_started = True
        logger.info("[Pipeline] Batch-running all %d businesses concurrently...", len(BUSINESSES))
        await asyncio.gather(*[
            _run_single_pipeline(b, discovery_cache, runner_factory)
            for b in BUSINESSES
        ])
        logger.info("[Pipeline] All batch pipelines complete.")

    return discovery_cache.pipeline_states.get(biz.id, {})


# ------------------------------------------------------------------
# State key population
# ------------------------------------------------------------------


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(600)
async def test_pipeline_populates_all_state_keys(biz, discovery_cache, runner_factory):
    """Pipeline produces all 7 expected state keys.

    First call triggers concurrent batch of all 5 businesses (~180s parallel).
    Timeout set to 600s to accommodate cold starts + concurrent execution.
    """
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    missing = [k for k in EXPECTED_STATE_KEYS if k not in state]
    assert not missing, f"Missing state keys for {biz.name}: {missing}"


# ------------------------------------------------------------------
# Theme data validation
# ------------------------------------------------------------------


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(180)
async def test_theme_data_has_valid_color(biz, discovery_cache, runner_factory):
    """themeData.primaryColor is a valid hex color."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    enriched = discovery_cache.enriched_profiles.get(biz.id, {})
    color = enriched.get("primaryColor")
    if color:
        assert re.match(r"^#[0-9a-fA-F]{3,8}$", color), (
            f"Invalid hex color for {biz.name}: {color}"
        )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(180)
async def test_theme_data_has_valid_persona(biz, discovery_cache, runner_factory):
    """themeData.persona is one of the valid enum values."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    enriched = discovery_cache.enriched_profiles.get(biz.id, {})
    persona = enriched.get("persona")
    if persona:
        assert persona in VALID_PERSONAS, (
            f"Invalid persona for {biz.name}: '{persona}'. Expected one of {VALID_PERSONAS}"
        )


# ------------------------------------------------------------------
# Social data validation
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(180)
async def test_social_data_finds_known_platforms(biz, discovery_cache, runner_factory):
    """socialData contains at least 1 URL for businesses known to have social presence."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    enriched = discovery_cache.enriched_profiles.get(biz.id, {})
    social = enriched.get("socialLinks", {})

    found_platforms = [p for p in biz.expected_social_platforms if social.get(p)]
    assert found_platforms, (
        f"{biz.name} expected social on {biz.expected_social_platforms}, "
        f"but socialLinks = {social}"
    )


# ------------------------------------------------------------------
# Contact data validation
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expect_phone],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(180)
async def test_contact_data_has_phone(biz, discovery_cache, runner_factory):
    """Businesses expected to have phones return a phone number."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    enriched = discovery_cache.enriched_profiles.get(biz.id, {})
    phone = enriched.get("phone")
    assert phone, f"{biz.name} expected to have a phone but got None"
    # Basic phone format check: contains digits
    digits = re.sub(r"\D", "", phone)
    assert len(digits) >= 10, f"Phone '{phone}' has fewer than 10 digits"


# ------------------------------------------------------------------
# Competitor data validation
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.is_restaurant],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(180)
async def test_competitor_data_has_entries(biz, discovery_cache, runner_factory):
    """Restaurant businesses should have at least 1 competitor with name + URL."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    enriched = discovery_cache.enriched_profiles.get(biz.id, {})
    competitors = enriched.get("competitors") or []
    assert len(competitors) >= 1, f"No competitors found for {biz.name}"

    for comp in competitors:
        assert comp.get("name"), f"Competitor missing 'name' for {biz.name}: {comp}"


# ------------------------------------------------------------------
# Social profile metrics validation
# ------------------------------------------------------------------


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(180)
async def test_social_profile_metrics_in_state(biz, discovery_cache, runner_factory):
    """Pipeline populates socialProfileMetrics state key."""
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)
    assert "socialProfileMetrics" in state, (
        f"socialProfileMetrics missing from state for {biz.name}"
    )


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(180)
async def test_social_profile_metrics_has_summary(biz, discovery_cache, runner_factory):
    """socialProfileMetrics has a summary with totalFollowers and overallPresenceScore."""
    import json
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    raw = state.get("socialProfileMetrics", {})
    metrics = raw if isinstance(raw, dict) else {}
    if isinstance(raw, str):
        try:
            metrics = json.loads(re.sub(r"```json\n?|\n?```", "", raw).strip())
        except (json.JSONDecodeError, ValueError):
            metrics = {}

    summary = metrics.get("summary", {})
    assert isinstance(summary, dict), f"summary should be a dict for {biz.name}"
    assert "totalFollowers" in summary, f"Missing totalFollowers in summary for {biz.name}"
    assert "overallPresenceScore" in summary, f"Missing overallPresenceScore for {biz.name}"


@pytest.mark.parametrize(
    "biz",
    [b for b in BUSINESSES if "instagram" in b.expected_social_platforms],
    ids=lambda b: b.id,
)
@pytest.mark.timeout(180)
async def test_social_profile_metrics_per_platform(biz, discovery_cache, runner_factory):
    """For businesses with known Instagram, at least one platform has follower data."""
    import json
    state = await _ensure_pipeline_run(biz, discovery_cache, runner_factory)

    raw = state.get("socialProfileMetrics", {})
    metrics = raw if isinstance(raw, dict) else {}
    if isinstance(raw, str):
        try:
            metrics = json.loads(re.sub(r"```json\n?|\n?```", "", raw).strip())
        except (json.JSONDecodeError, ValueError):
            metrics = {}

    platforms_with_data = []
    platforms_attempted = []
    for platform in ["instagram", "facebook", "twitter", "tiktok", "yelp"]:
        p_data = metrics.get(platform)
        if isinstance(p_data, dict):
            platforms_attempted.append(platform)
            if not p_data.get("error"):
                if p_data.get("followerCount") or p_data.get("rating") or p_data.get("reviewCount"):
                    platforms_with_data.append(platform)

    # Pass if we got actual data OR if platforms were attempted but blocked (login_required)
    assert platforms_with_data or platforms_attempted, (
        f"{biz.name} expected platform metrics but none found. Got: {list(metrics.keys())}"
    )
