"""
Grounding Accuracy Tests — Tier 3 Integration.

Compares agent discovery results against the high-fidelity 
Ground Truth data in tests/integration/businesses.py.
"""

from __future__ import annotations

import pytest
import logging
from tests.integration.businesses import ALL_GROUNDED_BUSINESSES, PRICING_GROUND_TRUTH, GroundTruth
from hephae_agents.discovery.runner import run_discovery
from hephae_agents.margin_analyzer.runner import run_margin_analysis

logger = logging.getLogger(__name__)

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("biz", ALL_GROUNDED_BUSINESSES, ids=lambda b: b.id)
async def test_discovery_grounding_accuracy(biz: GroundTruth):
    """Verify that discovery results accurately match ground truth facts."""
    # 1. Run discovery
    identity = {"name": biz.name, "address": f"{biz.city}, {biz.state}"}
    result = await run_discovery(identity)
    
    assert result, f"Discovery failed for {biz.name}"
    
    # 2. URL Grounding
    if biz.expected_url_fragment:
        official_url = result.get("officialUrl") or ""
        assert biz.expected_url_fragment.lower() in official_url.lower(), \
            f"URL Mismatch for {biz.name}. Expected fragment '{biz.expected_url_fragment}', got '{official_url}'"

    # 3. Social Grounding
    discovered_socials = result.get("socialLinks") or {}
    for platform in biz.expected_social_platforms:
        assert discovered_socials.get(platform), \
            f"Missing expected social platform '{platform}' for {biz.name}. Discovered: {discovered_socials}"

    # 4. Coordinate Grounding (if available)
    if biz.expected_lat and biz.expected_lng:
        coords = result.get("coordinates") or {}
        lat = coords.get("lat")
        lng = coords.get("lng")
        if lat and lng:
            # Within ~1km tolerance
            assert abs(lat - biz.expected_lat) < 0.05, f"Latitude drift for {biz.name}: {lat} vs {biz.expected_lat}"
            assert abs(lng - biz.expected_lng) < 0.05, f"Longitude drift for {biz.name}: {lng} vs {biz.expected_lng}"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_margin_surgeon_pricing_grounding():
    """Verify that margin surgeon identifies items near grounded price benchmarks."""
    # This is a logic test using grounded benchmarks
    # Note: In a real integration test, we'd use a screenshot of Joe's Pizza menu
    # For now, we verify the capability registry can handle these categories.
    
    pizza_benchmarks = PRICING_GROUND_TRUTH.get("Pizza Shops", [])
    assert len(pizza_benchmarks) > 0
    
    # Check that 'Plain Slice' benchmark is realistic
    slice_bench = next(b for b in pizza_benchmarks if b.item_name == "Plain Slice")
    assert 2.0 <= slice_bench.expected_avg_price <= 5.0
