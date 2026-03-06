"""
Unit tests for backend/lib/business_context.py

Covers: BusinessContext dataclass, build_business_context orchestrator,
in-memory cache, market data accessors, zip code parsing.
"""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from backend.lib.business_context import (
    BusinessContext,
    build_business_context,
    clear_context_cache,
    _parse_zip_code,
    _infer_region,
    _context_store,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_IDENTITY = {
    "name": "Test Restaurant",
    "address": "123 Main St, Nutley, NJ 07110",
    "officialUrl": "https://testrestaurant.com",
    "competitors": [{"name": "Rival", "url": "https://rival.com"}],
    "hours": "Mon-Fri 11am-10pm",
}


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the context cache before each test."""
    clear_context_cache()
    yield
    clear_context_cache()


# ---------------------------------------------------------------------------
# BusinessContext dataclass
# ---------------------------------------------------------------------------

class TestBusinessContext:
    def test_basic_properties(self):
        ctx = BusinessContext(slug="test-restaurant", identity=SAMPLE_IDENTITY)
        assert ctx.name == "Test Restaurant"
        assert ctx.address == "123 Main St, Nutley, NJ 07110"
        assert ctx.official_url == "https://testrestaurant.com"
        assert len(ctx.competitors) == 1
        assert ctx.hours == "Mon-Fri 11am-10pm"

    def test_has_admin_data_false(self):
        ctx = BusinessContext(slug="test", identity={})
        assert ctx.has_admin_data is False

    def test_has_admin_data_with_zipcode(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            zipcode_research={"sections": {"demographics": {}}},
        )
        assert ctx.has_admin_data is True

    def test_has_admin_data_with_area(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            area_research={"marketOpportunity": "High"},
        )
        assert ctx.has_admin_data is True

    def test_get_cpi_from_food_pricing(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            food_pricing_context={"blsCpiData": {"rate": 3.2}},
        )
        assert ctx.get_cpi() == {"rate": 3.2}

    def test_get_cpi_from_area_research(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            area_research={"industryIntelligence": {"blsCpiData": {"rate": 2.8}}},
        )
        assert ctx.get_cpi() == {"rate": 2.8}

    def test_get_cpi_from_prefetched(self):
        ctx = BusinessContext(slug="test", identity={}, cpi_data={"rate": 3.0})
        assert ctx.get_cpi() == {"rate": 3.0}

    def test_get_commodity_from_food_pricing(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            food_pricing_context={"usdaPriceData": {"eggs": 5.0}},
        )
        assert ctx.get_commodity_data() == {"eggs": 5.0}

    def test_get_commodity_from_prefetched(self):
        ctx = BusinessContext(
            slug="test",
            identity={},
            commodity_prices={"eggs": {"price": 5.0}},
        )
        assert ctx.get_commodity_data() == {"eggs": {"price": 5.0}}

    def test_get_fred(self):
        ctx = BusinessContext(slug="test", identity={}, fred_data={"rate": 3.5})
        assert ctx.get_fred() == {"rate": 3.5}

    def test_to_prompt_context_basic(self):
        ctx = BusinessContext(slug="test", identity={"name": "Test"})
        text = ctx.to_prompt_context()
        assert "Business Identity" in text
        assert "Test" in text

    def test_to_prompt_context_with_admin(self):
        ctx = BusinessContext(
            slug="test",
            identity={"name": "Test"},
            zipcode_research={"sections": {"demographics": {"pop": 10000}}},
            area_research={"marketOpportunity": "Growing"},
        )
        text = ctx.to_prompt_context()
        assert "Zip Code Research" in text
        assert "Area Research" in text


# ---------------------------------------------------------------------------
# Zip code parsing
# ---------------------------------------------------------------------------

class TestZipCodeParsing:
    def test_from_stored_field(self):
        assert _parse_zip_code("123 Main St", "07110") == "07110"

    def test_from_address(self):
        assert _parse_zip_code("123 Main St, Nutley, NJ 07110") == "07110"

    def test_from_address_with_plus4(self):
        assert _parse_zip_code("123 Main St, Nutley, NJ 07110-1234") == "07110"

    def test_none_when_missing(self):
        assert _parse_zip_code(None) is None
        assert _parse_zip_code("No zip here") is None


# ---------------------------------------------------------------------------
# Region inference
# ---------------------------------------------------------------------------

class TestInferRegion:
    def test_south(self):
        assert _infer_region("123 Main St, Miami, FL") == "South"

    def test_midwest(self):
        assert _infer_region("456 Oak Ave, Chicago, IL") == "Midwest"

    def test_west(self):
        assert _infer_region("789 Pine Rd, San Jose, CA") == "West"

    def test_northeast_default(self):
        assert _infer_region("321 Elm St, New York, NY") == "Northeast"

    def test_empty_defaults_to_northeast(self):
        assert _infer_region("") == "Northeast"


# ---------------------------------------------------------------------------
# build_business_context
# ---------------------------------------------------------------------------

class TestBuildBusinessContext:
    @pytest.mark.asyncio
    async def test_returns_context_for_identity_with_name(self):
        with (
            patch("backend.lib.business_context.read_business", return_value=None),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=None),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=None),
        ):
            ctx = await build_business_context(SAMPLE_IDENTITY, capabilities=["traffic"])
            assert ctx.slug == "test-restaurant"
            assert ctx.identity["name"] == "Test Restaurant"
            assert ctx.zip_code == "07110"

    @pytest.mark.asyncio
    async def test_returns_unknown_slug_for_no_name(self):
        ctx = await build_business_context({}, capabilities=["traffic"])
        assert ctx.slug == "unknown"

    @pytest.mark.asyncio
    async def test_merges_stored_business_data(self):
        stored = {
            "name": "Test Restaurant",
            "officialUrl": "https://stored-url.com",
            "hours": "Mon-Sun 9am-11pm",
            "createdAt": "2025-01-01",
            "updatedAt": "2025-01-02",
        }
        with (
            patch("backend.lib.business_context.read_business", return_value=stored),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=None),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=None),
        ):
            ctx = await build_business_context(SAMPLE_IDENTITY, capabilities=["traffic"])
            # Request identity overrides stored
            assert ctx.identity["officialUrl"] == "https://testrestaurant.com"
            # Metadata stripped
            assert "createdAt" not in ctx.identity

    @pytest.mark.asyncio
    async def test_loads_admin_data(self):
        zip_report = {"sections": {"demographics": {"population": 30000}}}
        area_report = {"marketOpportunity": "High growth area"}
        with (
            patch("backend.lib.business_context.read_business", return_value=None),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=zip_report),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=area_report),
        ):
            ctx = await build_business_context(SAMPLE_IDENTITY, capabilities=["competitive"])
            assert ctx.zipcode_research == zip_report
            assert ctx.area_research == area_report
            assert ctx.has_admin_data is True

    @pytest.mark.asyncio
    async def test_prefetches_market_data_when_no_admin(self):
        with (
            patch("backend.lib.business_context.read_business", return_value=None),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=None),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=None),
            patch("backend.agents.market_data.fetch_cpi_data", new_callable=AsyncMock, return_value={"rate": 3.0}),
            patch("backend.agents.market_data.fetch_fred_indicators", new_callable=AsyncMock, return_value={"rate": 3.5}),
            patch("backend.agents.market_data.fetch_commodity_prices", new_callable=AsyncMock, return_value={"commodity": "eggs", "price": 5.0}),
        ):
            ctx = await build_business_context(SAMPLE_IDENTITY, capabilities=["margin"])
            assert ctx.cpi_data == {"rate": 3.0}
            assert ctx.fred_data == {"rate": 3.5}
            assert "eggs" in ctx.commodity_prices

    @pytest.mark.asyncio
    async def test_cache_hit_merges_identity(self):
        with (
            patch("backend.lib.business_context.read_business", return_value=None),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=None),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=None),
        ):
            # First call — populates cache
            ctx1 = await build_business_context(
                {"name": "Test Restaurant", "competitors": []}, capabilities=["traffic"]
            )
            assert ctx1.identity.get("competitors") == []

            # Second call with competitors — cache hit should merge
            ctx2 = await build_business_context(
                {**SAMPLE_IDENTITY}, capabilities=["competitive"]
            )
            assert len(ctx2.identity["competitors"]) == 1
            assert ctx2 is ctx1  # same object from cache

    @pytest.mark.asyncio
    async def test_skips_market_prefetch_with_admin_data(self):
        stored = {
            "name": "Test Restaurant",
            "foodPricingContext": {"blsCpiData": {"rate": 2.5}},
        }
        with (
            patch("backend.lib.business_context.read_business", return_value=stored),
            patch("backend.lib.business_context.get_zipcode_report", new_callable=AsyncMock, return_value=None),
            patch("backend.lib.business_context.get_area_research_for_zip", new_callable=AsyncMock, return_value=None),
        ):
            ctx = await build_business_context(SAMPLE_IDENTITY, capabilities=["margin"])
            # Should use admin food pricing, not pre-fetch
            assert ctx.food_pricing_context == {"blsCpiData": {"rate": 2.5}}
            assert ctx.cpi_data is None  # not pre-fetched


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

class TestCacheManagement:
    def test_clear_specific_slug(self):
        _context_store["test-slug"] = (
            BusinessContext(slug="test-slug", identity={}),
            time.time(),
        )
        _context_store["other-slug"] = (
            BusinessContext(slug="other-slug", identity={}),
            time.time(),
        )
        clear_context_cache("test-slug")
        assert "test-slug" not in _context_store
        assert "other-slug" in _context_store

    def test_clear_all(self):
        _context_store["a"] = (BusinessContext(slug="a", identity={}), time.time())
        _context_store["b"] = (BusinessContext(slug="b", identity={}), time.time())
        clear_context_cache()
        assert len(_context_store) == 0
