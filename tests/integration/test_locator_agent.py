"""
Level 2: LocatorAgent resolves correct business identity.

Validates that LocatorAgent.resolve() returns:
- Name containing expected substring
- Address mentioning city/state
- URL containing expected fragment
- Coordinates within tolerance of known location
"""

from __future__ import annotations

import pytest

from hephae_agents.discovery.locator import LocatorAgent
from tests.integration.businesses import BUSINESSES, GroundTruth

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_locator_resolves_name(biz: GroundTruth, discovery_cache):
    """LocatorAgent returns a name containing the expected fragment."""
    result = await LocatorAgent.resolve(biz.query)
    discovery_cache.locator_results[biz.id] = result

    name = result.get("name", "")
    assert biz.expected_name_fragment.lower() in name.lower(), (
        f"Expected '{biz.expected_name_fragment}' in name, got: '{name}'"
    )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_locator_resolves_url(biz: GroundTruth, discovery_cache):
    """LocatorAgent returns a URL containing the expected fragment."""
    if biz.id not in discovery_cache.locator_results:
        result = await LocatorAgent.resolve(biz.query)
        discovery_cache.locator_results[biz.id] = result

    result = discovery_cache.locator_results[biz.id]
    url = result.get("officialUrl", "")
    assert biz.expected_url_fragment.lower() in url.lower(), (
        f"Expected '{biz.expected_url_fragment}' in URL, got: '{url}'"
    )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_locator_resolves_address(biz: GroundTruth, discovery_cache):
    """LocatorAgent returns an address mentioning the city or state."""
    if biz.id not in discovery_cache.locator_results:
        result = await LocatorAgent.resolve(biz.query)
        discovery_cache.locator_results[biz.id] = result

    result = discovery_cache.locator_results[biz.id]
    address = (result.get("address") or "").lower()
    city_match = biz.city.lower() in address
    state_match = biz.state.lower() in address
    assert city_match or state_match, (
        f"Expected '{biz.city}' or '{biz.state}' in address, got: '{address}'"
    )


@pytest.mark.parametrize("biz", BUSINESSES, ids=lambda b: b.id)
@pytest.mark.timeout(60)
async def test_locator_resolves_coordinates(biz: GroundTruth, discovery_cache):
    """LocatorAgent returns coordinates within tolerance of known location."""
    if biz.id not in discovery_cache.locator_results:
        result = await LocatorAgent.resolve(biz.query)
        discovery_cache.locator_results[biz.id] = result

    result = discovery_cache.locator_results[biz.id]
    coords = result.get("coordinates")
    assert coords is not None, f"No coordinates returned for {biz.name}"

    lat = coords.get("lat", 0)
    lng = coords.get("lng", 0)
    assert abs(lat - biz.expected_lat) < biz.coord_tolerance, (
        f"Lat {lat} too far from expected {biz.expected_lat} (tolerance {biz.coord_tolerance})"
    )
    assert abs(lng - biz.expected_lng) < biz.coord_tolerance, (
        f"Lng {lng} too far from expected {biz.expected_lng} (tolerance {biz.coord_tolerance})"
    )
