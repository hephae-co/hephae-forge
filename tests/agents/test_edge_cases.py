"""Edge case tests for businesses without traditional websites.

Tier 1: Fast, mocked — validates that the pipeline handles adversarial
inputs correctly (no-website, aggregator sites, missing data).
"""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Discovery runner: no-website businesses
# ---------------------------------------------------------------------------


class TestDiscoveryRunnerNoWebsite:
    """Discovery runner should gracefully handle missing officialUrl."""

    @pytest.mark.asyncio
    async def test_no_url_skips_phase1(self):
        """When officialUrl is empty, Phase 1 (crawl + entity match) is skipped."""
        from hephae_agents.discovery.runner import run_discovery

        identity = {"name": "Cupily Coffeehouse", "address": "Nutley, NJ 07110", "officialUrl": ""}

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session.id = "test-session"
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_service.update_session = AsyncMock()

        async def _empty_stream(*args, **kwargs):
            return
            yield

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = MagicMock(side_effect=_empty_stream)

        with (
            patch("hephae_db.firestore.session_service.FirestoreSessionService", return_value=mock_session_service),
            patch("hephae_agents.discovery.runner.Runner", return_value=mock_runner_instance) as mock_runner_cls,
            patch("hephae_agents.discovery.runner._fetch_local_context", new_callable=AsyncMock, return_value=None),
        ):
            result = await run_discovery(identity)

        # Phase 2 runner should still be called (search-based discovery)
        assert mock_runner_cls.call_count >= 1, "Phase 2 runner should have been called"
        # Result should contain identity fields
        assert result["name"] == "Cupily Coffeehouse"
        # Entity match should be None (skipped for no-URL)
        assert result.get("entityMatch") is None or result.get("entityMatch") == {}

    @pytest.mark.asyncio
    async def test_no_url_does_not_raise(self):
        """Empty officialUrl should NOT raise ValueError."""
        from hephae_agents.discovery.runner import run_discovery

        identity = {"name": "Test Business", "address": "123 Main St", "officialUrl": ""}

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session.id = "test-session"
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_service.update_session = AsyncMock()

        async def _empty_stream(*args, **kwargs):
            return
            yield

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = MagicMock(side_effect=_empty_stream)

        with (
            patch("hephae_db.firestore.session_service.FirestoreSessionService", return_value=mock_session_service),
            patch("hephae_agents.discovery.runner.Runner", return_value=mock_runner_instance),
            patch("hephae_agents.discovery.runner._fetch_local_context", new_callable=AsyncMock, return_value=None),
        ):
            # Should not raise
            result = await run_discovery(identity)
            assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Discovery runner: entity match abort
# ---------------------------------------------------------------------------


class TestDiscoveryRunnerEntityMatch:
    """Discovery runner should abort on MISMATCH/AGGREGATOR entity match."""

    @pytest.mark.asyncio
    async def test_aggregator_aborts_discovery(self):
        """When entity match returns AGGREGATOR, discovery should abort."""
        from hephae_agents.discovery.runner import run_discovery

        identity = {
            "name": "Test Restaurant",
            "address": "123 Main St",
            "officialUrl": "https://www.doordash.com/store/test-restaurant",
        }

        mock_session = MagicMock()
        mock_session.state = {
            "entityMatchResult": json.dumps({
                "status": "AGGREGATOR",
                "reason": "URL points to DoorDash delivery platform, not the business's own website",
            }),
            "rawSiteData": "Some crawled content",
        }
        mock_session.id = "test-session"
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_service.update_session = AsyncMock()

        async def _empty_stream(*args, **kwargs):
            return
            yield

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = MagicMock(side_effect=_empty_stream)

        with (
            patch("hephae_db.firestore.session_service.FirestoreSessionService", return_value=mock_session_service),
            patch("hephae_agents.discovery.runner.Runner", return_value=mock_runner_instance),
            patch("hephae_agents.discovery.runner._fetch_local_context", new_callable=AsyncMock, return_value=None),
        ):
            result = await run_discovery(identity)

        assert result.get("discoveryAborted") is True
        assert result.get("entityMatch", {}).get("status") == "AGGREGATOR"

    @pytest.mark.asyncio
    async def test_mismatch_aborts_discovery(self):
        """When entity match returns MISMATCH, discovery should abort."""
        from hephae_agents.discovery.runner import run_discovery

        identity = {
            "name": "Mario's Pizza",
            "address": "456 Oak Ave",
            "officialUrl": "https://www.dentistoffice.com",
        }

        mock_session = MagicMock()
        mock_session.state = {
            "entityMatchResult": json.dumps({
                "status": "MISMATCH",
                "reason": "Website is for a dental office, not a pizza restaurant",
            }),
            "rawSiteData": "Welcome to Dr. Smith's Dental Office",
        }
        mock_session.id = "test-session"
        mock_session_service = AsyncMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_service.update_session = AsyncMock()

        async def _empty_stream(*args, **kwargs):
            return
            yield

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = MagicMock(side_effect=_empty_stream)

        with (
            patch("hephae_db.firestore.session_service.FirestoreSessionService", return_value=mock_session_service),
            patch("hephae_agents.discovery.runner.Runner", return_value=mock_runner_instance),
            patch("hephae_agents.discovery.runner._fetch_local_context", new_callable=AsyncMock, return_value=None),
        ):
            result = await run_discovery(identity)

        assert result.get("discoveryAborted") is True
        assert result.get("entityMatch", {}).get("status") == "MISMATCH"


# ---------------------------------------------------------------------------
# Enrichment phase: no-website businesses
# ---------------------------------------------------------------------------


class TestEnrichmentNoWebsite:
    """Enrichment should still call run_discovery even without a website."""

    @pytest.mark.asyncio
    async def test_enrichment_runs_discovery_without_website(self):
        """enrich_business_profile calls run_discovery even when website is empty."""
        from hephae_api.workflows.phases.enrichment import enrich_business_profile

        mock_biz = {"name": "Test Cafe", "website": ""}
        mock_result = {
            "name": "Test Cafe",
            "socialLinks": {"instagram": "https://instagram.com/testcafe"},
            "competitors": [{"name": "Rival Cafe"}],
        }

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=mock_biz),
            patch("hephae_agents.discovery.runner.run_discovery", new_callable=AsyncMock, return_value=mock_result) as mock_discovery,
            patch("hephae_api.workflows.phases.enrichment._find_website", new_callable=AsyncMock, return_value=""),
        ):
            result = await enrich_business_profile("Test Cafe", "123 Main St", "test-cafe")

        mock_discovery.assert_called_once()
        assert result is not None
        assert result["socialLinks"]["instagram"] == "https://instagram.com/testcafe"


# ---------------------------------------------------------------------------
# Capability registry: should_run guards
# ---------------------------------------------------------------------------


class TestCapabilityGuards:
    """Capabilities with should_run guards skip cleanly for edge cases."""

    def test_seo_skips_without_url(self):
        from hephae_api.workflows.capabilities.registry import get_enabled_capabilities

        caps = get_enabled_capabilities()
        seo = next(c for c in caps if c.name == "seo")
        assert seo.should_run is not None

        # No officialUrl → should not run
        assert not seo.should_run({"name": "Test", "officialUrl": ""})
        assert not seo.should_run({"name": "Test"})
        # With officialUrl → should run
        assert seo.should_run({"name": "Test", "officialUrl": "https://example.com"})

    def test_competitive_skips_without_competitors(self):
        from hephae_api.workflows.capabilities.registry import get_enabled_capabilities

        caps = get_enabled_capabilities()
        comp = next(c for c in caps if c.name == "competitive")
        assert comp.should_run is not None

        # No competitors → should not run
        assert not comp.should_run({"name": "Test", "competitors": []})
        assert not comp.should_run({"name": "Test"})
        # With competitors → should run
        assert comp.should_run({"name": "Test", "competitors": [{"name": "Rival"}]})

    def test_margin_skips_without_menu_screenshot(self):
        from hephae_api.workflows.capabilities.registry import get_enabled_capabilities

        caps = get_enabled_capabilities()
        margin = next(c for c in caps if c.name == "margin_surgeon")
        assert margin.should_run is not None

        # No screenshot → should not run
        assert not margin.should_run({"name": "Test"})
        assert not margin.should_run({"name": "Test", "menuScreenshotBase64": ""})
        # With screenshot → should run
        assert margin.should_run({"name": "Test", "menuScreenshotBase64": "data:image/png;base64,abc123"})

    def test_traffic_and_social_run_without_url(self):
        """Traffic and Social should run even for no-website businesses."""
        from hephae_api.workflows.capabilities.registry import get_enabled_capabilities

        caps = get_enabled_capabilities()
        traffic = next(c for c in caps if c.name == "traffic")
        social = next(c for c in caps if c.name == "social")

        no_website_biz = {"name": "Instagram Only Cafe", "address": "123 Main St"}

        # Traffic has no should_run guard → runs for all
        assert traffic.should_run is None or traffic.should_run(no_website_biz)
        # Social has no should_run guard → runs for all
        assert social.should_run is None or social.should_run(no_website_biz)


# ---------------------------------------------------------------------------
# Discovery runner: zip code extraction
# ---------------------------------------------------------------------------


class TestZipCodeExtraction:
    """Zip code is correctly extracted from various identity formats."""

    def test_extract_from_zip_code_field(self):
        from hephae_agents.discovery.runner import _extract_zip_code

        assert _extract_zip_code({"zipCode": "07110"}) == "07110"
        assert _extract_zip_code({"zip_code": "07003"}) == "07003"
        assert _extract_zip_code({"zip": "10001"}) == "10001"

    def test_extract_from_address(self):
        from hephae_agents.discovery.runner import _extract_zip_code

        assert _extract_zip_code({"address": "123 Main St, Nutley, NJ 07110"}) == "07110"
        assert _extract_zip_code({"address": "456 Oak Ave, NYC, NY 10001-1234"}) == "10001"

    def test_returns_none_when_missing(self):
        from hephae_agents.discovery.runner import _extract_zip_code

        assert _extract_zip_code({}) is None
        assert _extract_zip_code({"address": "No zip here"}) is None


# ---------------------------------------------------------------------------
# Discovery runner: safe parse helpers
# ---------------------------------------------------------------------------


class TestSafeParse:
    """_safe_parse and _safe_parse_array handle malformed input."""

    def test_safe_parse_dict_passthrough(self):
        from hephae_agents.discovery.runner import _safe_parse
        assert _safe_parse({"key": "val"}) == {"key": "val"}

    def test_safe_parse_json_string(self):
        from hephae_agents.discovery.runner import _safe_parse
        assert _safe_parse('{"key": "val"}') == {"key": "val"}

    def test_safe_parse_markdown_fenced(self):
        from hephae_agents.discovery.runner import _safe_parse
        assert _safe_parse('```json\n{"key": "val"}\n```') == {"key": "val"}

    def test_safe_parse_invalid(self):
        from hephae_agents.discovery.runner import _safe_parse
        assert _safe_parse("not json") == {}
        assert _safe_parse(None) == {}
        assert _safe_parse(42) == {}

    def test_safe_parse_array(self):
        from hephae_agents.discovery.runner import _safe_parse_array
        assert _safe_parse_array([1, 2]) == [1, 2]
        assert _safe_parse_array('[1, 2]') == [1, 2]
        assert _safe_parse_array('```json\n[1, 2]\n```') == [1, 2]
        assert _safe_parse_array('{"not": "array"}') == []
        assert _safe_parse_array("bad") == []
