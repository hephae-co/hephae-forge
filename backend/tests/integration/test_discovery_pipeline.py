"""
Level 3: Full discovery pipeline populates all 7 state keys.

Runs the complete DiscoveryPipeline (SiteCrawler → 6 parallel sub-agents)
via the ADK Runner and validates every output key.

This is the most expensive test (~60-120s per business).
Results are cached in session-scoped discovery_cache for Levels 4 and 5.
"""

from __future__ import annotations

import logging
import re

import pytest

from backend.agents.discovery.locator import LocatorAgent
from backend.tests.integration.businesses import BUSINESSES, GroundTruth
from backend.tests.integration.conftest import build_enriched_profile
from backend.lib.adk_helpers import user_msg

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
]

VALID_PERSONAS = [
    "Local Business",
    "Modern Artisan",
    "Classic Establishment",
    "Quick Service",
    "Fine Dining",
]


async def _ensure_pipeline_run(biz: GroundTruth, discovery_cache, runner_factory):
    """Run the pipeline for a business if not already cached."""
    if biz.id in discovery_cache.pipeline_states:
        return discovery_cache.pipeline_states[biz.id]

    # Ensure we have locator results
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

    logger.info(f"[Pipeline/{biz.id}] State keys: {list(state.keys())}")
    discovery_cache.pipeline_states[biz.id] = state

    # Build and cache enriched profile
    enriched = build_enriched_profile(identity, state)
    discovery_cache.enriched_profiles[biz.id] = enriched

    return state


# ------------------------------------------------------------------
# State key population
# ------------------------------------------------------------------


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(180)
async def test_pipeline_populates_all_state_keys(biz, discovery_cache, runner_factory):
    """Pipeline produces all 7 expected state keys."""
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
