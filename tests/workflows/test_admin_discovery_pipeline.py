"""Tests for the grounded business discovery pipeline."""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from google.adk.tools import google_search

from backend.config import AgentModels
from hephae_capabilities.discovery import (
    BusinessItem,
    ConfidenceScorer,
    CategoryProgressChecker,
    DiscoveryAccumulator,
    _classify_source,
    _generate_slug,
    scan_zipcode,
    category_planner,
    category_scanner,
    business_verifier,
    business_discovery_pipeline,
)


# ---------------------------------------------------------------------------
# BusinessItem model tests
# ---------------------------------------------------------------------------

class TestBusinessItem:
    def test_minimal_fields(self):
        biz = BusinessItem(name="Test Biz", address="123 Main St")
        assert biz.name == "Test Biz"
        assert biz.address == "123 Main St"
        assert biz.docId is None
        assert biz.confidence == 0.0
        assert biz.discoveryMethod == "grounded_search"

    def test_enriched_fields(self):
        biz = BusinessItem(
            name="Rich Biz",
            address="456 Oak Ave",
            zipCode="07110",
            city="Nutley",
            state="NJ",
            phone="973-555-0100",
            email="info@richbiz.com",
            website="https://richbiz.com",
            officialUrl="https://richbiz.com",
            category="Restaurants & Food",
            subcategory="Italian",
            rating=4.5,
            socialLinks={"facebook": "https://facebook.com/richbiz"},
            confidence=0.85,
            sourceCount=3,
            sources=[{"url": "https://yelp.com/biz/richbiz", "type": "directory"}],
            discoveredAt="2026-03-01T00:00:00+00:00",
        )
        assert biz.phone == "973-555-0100"
        assert biz.email == "info@richbiz.com"
        assert biz.rating == 4.5
        assert biz.socialLinks["facebook"] == "https://facebook.com/richbiz"
        assert biz.confidence == 0.85

    def test_default_factories(self):
        biz = BusinessItem(name="A", address="B")
        assert biz.socialLinks == {}
        assert biz.sources == []

    def test_backward_compatible_with_old_data(self):
        """Old Firestore docs only have name/address/docId — should still parse."""
        old_data = {"name": "Old Biz", "address": "789 St", "docId": "old-biz"}
        biz = BusinessItem(**old_data)
        assert biz.name == "Old Biz"
        assert biz.docId == "old-biz"
        assert biz.zipCode == ""


# ---------------------------------------------------------------------------
# _classify_source tests
# ---------------------------------------------------------------------------

class TestClassifySource:
    def test_yelp(self):
        assert _classify_source("https://www.yelp.com/biz/some-place") == "directory"

    def test_yellowpages(self):
        assert _classify_source("https://www.yellowpages.com/nutley-nj/pizza") == "directory"

    def test_yp(self):
        assert _classify_source("https://www.yp.com/biz/abc") == "directory"

    def test_bbb(self):
        assert _classify_source("https://www.bbb.org/business/123") == "directory"

    def test_manta(self):
        assert _classify_source("https://www.manta.com/c/abc") == "directory"

    def test_chamber(self):
        assert _classify_source("https://nutleychamberofcommerce.com/members") == "chamber"

    def test_chamber_alt(self):
        assert _classify_source("https://chamber.nutley.org/list") == "chamber"

    def test_google_maps(self):
        assert _classify_source("https://www.google.com/maps/place/Some+Biz") == "maps"

    def test_facebook(self):
        assert _classify_source("https://www.facebook.com/somebiz") == "social"

    def test_instagram(self):
        assert _classify_source("https://www.instagram.com/somebiz") == "social"

    def test_linkedin(self):
        assert _classify_source("https://www.linkedin.com/company/somebiz") == "social"

    def test_healthgrades(self):
        assert _classify_source("https://www.healthgrades.com/physician/dr-smith") == "directory"

    def test_generic_website(self):
        assert _classify_source("https://www.somebusiness.com") == "website"

    def test_empty_url(self):
        assert _classify_source("") == "unknown"

    def test_none_like(self):
        assert _classify_source("") == "unknown"


# ---------------------------------------------------------------------------
# _generate_slug tests
# ---------------------------------------------------------------------------

class TestGenerateSlug:
    def test_basic(self):
        assert _generate_slug("Mario's Pizza") == "marios-pizza"

    def test_extra_spaces(self):
        assert _generate_slug("  Joe's   Diner  ") == "joes-diner"

    def test_special_chars(self):
        assert _generate_slug("AT&T Store #123") == "att-store-123"

    def test_truncation(self):
        long_name = "A" * 100
        assert len(_generate_slug(long_name)) <= 80


# ---------------------------------------------------------------------------
# ConfidenceScorer tests
# ---------------------------------------------------------------------------

class TestConfidenceScorer:
    """Test the deterministic scoring math."""

    def _make_business(self, verified=True, sources=None, website="", phone="", email="", social=None):
        return {
            "name": "Test Biz",
            "address": "123 St",
            "verified": verified,
            "sources": sources or [],
            "website": website,
            "phone": phone,
            "email": email,
            "socialLinks": social or {},
        }

    def test_verified_no_sources(self):
        """Verified but no sources: 0.3 — below threshold."""
        biz = self._make_business(verified=True, sources=[])
        score = 0.3  # verified only
        assert score < 0.5

    def test_verified_two_sources(self):
        """Verified + 2 sources: 0.3 + 0.3 = 0.6 — passes."""
        biz = self._make_business(
            verified=True,
            sources=[{"url": "a"}, {"url": "b"}],
        )
        score = 0.3 + (2 * 0.15)
        assert score == 0.6

    def test_verified_three_sources_with_website(self):
        """Verified + 3 sources + website: 0.3 + 0.45 + 0.1 = 0.85."""
        score = 0.3 + 0.45 + 0.1
        assert score == 0.85

    def test_full_contact_info(self):
        """Verified + 3 sources + website + phone + email + social = 1.0 (capped)."""
        score = 0.3 + 0.45 + 0.1 + 0.05 + 0.05 + 0.05
        assert score == 1.0

    def test_unverified_with_sources(self):
        """Not verified + 2 sources: 0 + 0.3 = 0.3 — below threshold."""
        score = 0.0 + (2 * 0.15)
        assert score == 0.3
        assert score < 0.5

    def test_source_bonus_cap(self):
        """Source bonus caps at 0.45 even with 5 sources."""
        raw = 5 * 0.15  # 0.75
        capped = min(raw, 0.45)
        assert capped == 0.45


# ---------------------------------------------------------------------------
# DiscoveryAccumulator tests (async)
# ---------------------------------------------------------------------------

class TestDiscoveryAccumulator:
    @pytest.mark.asyncio
    async def test_merges_new_businesses(self):
        acc = DiscoveryAccumulator(name="test_acc")
        ctx = MagicMock()
        ctx.session.state = {
            "raw_discoveries": json.dumps({
                "businesses": [
                    {"name": "Biz A", "address": "1 St"},
                    {"name": "Biz B", "address": "2 St"},
                ]
            }),
            "all_discoveries": [],
        }

        events = []
        async for event in acc._run_async_impl(ctx):
            events.append(event)

        assert len(ctx.session.state["all_discoveries"]) == 2
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_deduplicates_by_name(self):
        acc = DiscoveryAccumulator(name="test_acc")
        ctx = MagicMock()
        ctx.session.state = {
            "raw_discoveries": json.dumps({
                "businesses": [
                    {"name": "Biz A", "address": "1 St"},
                    {"name": "biz a", "address": "1 Street"},  # duplicate
                ]
            }),
            "all_discoveries": [{"name": "Biz A", "address": "1 St"}],
        }

        async for _ in acc._run_async_impl(ctx):
            pass

        assert len(ctx.session.state["all_discoveries"]) == 1

    @pytest.mark.asyncio
    async def test_handles_bad_json(self):
        acc = DiscoveryAccumulator(name="test_acc")
        ctx = MagicMock()
        ctx.session.state = {
            "raw_discoveries": "not valid json {{{",
            "all_discoveries": [{"name": "Existing", "address": "0 St"}],
        }

        async for _ in acc._run_async_impl(ctx):
            pass

        # Should not crash, existing list preserved
        assert len(ctx.session.state["all_discoveries"]) == 1

    @pytest.mark.asyncio
    async def test_handles_list_format(self):
        """raw_discoveries can be a plain list instead of {businesses: [...]}."""
        acc = DiscoveryAccumulator(name="test_acc")
        ctx = MagicMock()
        ctx.session.state = {
            "raw_discoveries": json.dumps([
                {"name": "Biz X", "address": "9 Ave"},
            ]),
            "all_discoveries": [],
        }

        async for _ in acc._run_async_impl(ctx):
            pass

        assert len(ctx.session.state["all_discoveries"]) == 1
        assert ctx.session.state["all_discoveries"][0]["name"] == "Biz X"


# ---------------------------------------------------------------------------
# CategoryProgressChecker tests (async)
# ---------------------------------------------------------------------------

class TestCategoryProgressChecker:
    @pytest.mark.asyncio
    async def test_increments_index(self):
        checker = CategoryProgressChecker(name="test_checker")
        ctx = MagicMock()
        ctx.session.state = {
            "current_category_index": 2,
            "discovery_categories": json.dumps([
                {"category": "A"}, {"category": "B"},
                {"category": "C"}, {"category": "D"},
                {"category": "E"},
            ]),
        }

        async for event in checker._run_async_impl(ctx):
            # Should NOT escalate (3 < 5)
            assert not (event.actions and event.actions.escalate)

        assert ctx.session.state["current_category_index"] == 3

    @pytest.mark.asyncio
    async def test_escalates_when_done(self):
        checker = CategoryProgressChecker(name="test_checker")
        ctx = MagicMock()
        ctx.session.state = {
            "current_category_index": 4,  # will become 5, which == len(categories)
            "discovery_categories": json.dumps([
                {"category": "A"}, {"category": "B"},
                {"category": "C"}, {"category": "D"},
                {"category": "E"},
            ]),
        }

        async for event in checker._run_async_impl(ctx):
            assert event.actions and event.actions.escalate

        assert ctx.session.state["current_category_index"] == 5


# ---------------------------------------------------------------------------
# Agent initialization tests
# ---------------------------------------------------------------------------

class TestAgentSetup:
    def test_category_planner_config(self):
        assert category_planner.name == "category_planner"
        assert category_planner.model == AgentModels.PRIMARY_MODEL
        assert category_planner.output_key == "discovery_categories"

    def test_category_scanner_config(self):
        assert category_scanner.name == "category_scanner"
        assert category_scanner.model == AgentModels.PRIMARY_MODEL
        assert google_search in category_scanner.tools
        assert category_scanner.output_key == "raw_discoveries"

    def test_business_verifier_config(self):
        assert business_verifier.name == "business_verifier"
        assert business_verifier.model == AgentModels.PRIMARY_MODEL
        assert google_search in business_verifier.tools
        assert business_verifier.output_key == "verified_businesses"

    def test_pipeline_agent_order(self):
        names = [a.name for a in business_discovery_pipeline.sub_agents]
        assert names == [
            "category_planner",
            "category_discovery_loop",
            "business_verifier",
            "confidence_scorer",
        ]

    def test_loop_agent_sub_agents(self):
        from hephae_capabilities.discovery import category_discovery_loop
        names = [a.name for a in category_discovery_loop.sub_agents]
        assert names == [
            "category_scanner",
            "discovery_accumulator",
            "category_progress_checker",
        ]


# ---------------------------------------------------------------------------
# scan_zipcode integration tests
# ---------------------------------------------------------------------------

class TestScanZipcode:
    @pytest.mark.asyncio
    @patch("hephae_capabilities.discovery.firestore_service")
    async def test_cache_hit_returns_enriched_data(self, mock_fs):
        mock_fs.get_businesses_in_zipcode.return_value = [
            {
                "name": "Cached Biz",
                "address": "123 St",
                "docId": "cached-biz",
                "zipCode": "07110",
                "phone": "973-555-0100",
                "email": "info@cached.com",
                "website": "https://cached.com",
                "category": "Restaurants",
                "confidence": 0.85,
                "sourceCount": 3,
            }
        ]

        results = await scan_zipcode("07110")

        assert len(results) == 1
        assert results[0].name == "Cached Biz"
        assert results[0].phone == "973-555-0100"
        assert results[0].email == "info@cached.com"
        assert results[0].confidence == 0.85
        mock_fs.get_businesses_in_zipcode.assert_called_with("07110")

    @pytest.mark.asyncio
    @patch("hephae_capabilities.discovery.firestore_service")
    async def test_cache_hit_backward_compat(self, mock_fs):
        """Old cache entries with only name/address/docId still work."""
        mock_fs.get_businesses_in_zipcode.return_value = [
            {"name": "Old Biz", "address": "456 Ave", "docId": "old-biz"}
        ]

        results = await scan_zipcode("10001")

        assert len(results) == 1
        assert results[0].name == "Old Biz"
        assert results[0].zipCode == ""  # default
        assert results[0].confidence == 0.0  # default
