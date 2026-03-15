"""Qualification pipeline tests — tools, scoring, threshold, phase integration, and edge cases."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from hephae_agents.qualification.chains import is_chain
from hephae_agents.qualification.tools import (
    domain_analyzer,
    platform_detector,
    pixel_detector,
    contact_path_detector,
    meta_extractor,
)
from hephae_agents.qualification.threshold import (
    compute_dynamic_threshold,
    extract_research_context,
)
from hephae_agents.qualification.scanner import (
    qualify_business,
    qualify_businesses,
    QualificationResult,
    QUALIFIED,
    PARKED,
    DISQUALIFIED,
    _score_business,
    _run_llm_classifier,
    _run_full_probe,
)


# ===========================================================================
# 1. Chain detection
# ===========================================================================


class TestChainDetection:
    def test_known_chains(self):
        assert is_chain("McDonald's") is True
        assert is_chain("Starbucks") is True
        assert is_chain("Subway") is True
        assert is_chain("Walmart") is True
        assert is_chain("Planet Fitness") is True

    def test_local_businesses(self):
        assert is_chain("Pizza Planet") is False
        assert is_chain("Main Street Cafe") is False
        assert is_chain("Tony's Barbershop") is False
        assert is_chain("Bella's Salon") is False

    def test_case_insensitive(self):
        assert is_chain("MCDONALDS") is True
        assert is_chain("starbucks") is True
        assert is_chain("Burger King") is True

    def test_with_suffix(self):
        assert is_chain("Starbucks Coffee") is True
        assert is_chain("Dominos Pizza") is True

    def test_chain_as_suffix(self):
        """Chain name at end of business name."""
        assert is_chain("The Starbucks") is True  # ends with " starbucks"
        assert is_chain("Local Subway") is True  # ends with " subway"

    def test_partial_name_no_false_positive(self):
        """Names that happen to contain chain words but are clearly different."""
        assert is_chain("Shelley's Kitchen") is False
        assert is_chain("Golden Gate Bistro") is False

    def test_empty_name(self):
        assert is_chain("") is False

    def test_unicode_name(self):
        assert is_chain("Café Bonheur") is False
        assert is_chain("Ñoño's Tacos") is False


# ===========================================================================
# 2. Domain analyzer
# ===========================================================================


class TestDomainAnalyzer:
    def test_custom_domain(self):
        result = domain_analyzer("https://tonys-pizza.com")
        assert result["domain_type"] == "custom"
        assert result["is_custom_domain"] is True
        assert result["is_https"] is True

    def test_directory_domain(self):
        result = domain_analyzer("https://www.yelp.com/biz/tonys-pizza")
        assert result["domain_type"] == "directory"
        assert result["is_custom_domain"] is False

    def test_social_domain(self):
        result = domain_analyzer("https://www.instagram.com/tonyspizza")
        assert result["domain_type"] == "social"
        assert result["is_custom_domain"] is False

    def test_platform_subdomain(self):
        result = domain_analyzer("https://tonys-pizza.myshopify.com")
        assert result["domain_type"] == "platform_subdomain"
        assert result["is_custom_domain"] is False

    def test_empty_url(self):
        result = domain_analyzer("")
        assert result["domain_type"] == "unknown"

    def test_http_not_https(self):
        result = domain_analyzer("http://example.com")
        assert result["is_https"] is False

    def test_no_protocol(self):
        result = domain_analyzer("example.com")
        assert result["domain"] == "example.com"
        assert result["is_https"] is True  # defaults to https

    def test_doordash_directory(self):
        result = domain_analyzer("https://www.doordash.com/store/test-123")
        assert result["domain_type"] == "directory"

    def test_grubhub_directory(self):
        result = domain_analyzer("https://www.grubhub.com/restaurant/test")
        assert result["domain_type"] == "directory"

    def test_x_social(self):
        result = domain_analyzer("https://x.com/mybusiness")
        assert result["domain_type"] == "social"


# ===========================================================================
# 3. Platform detector
# ===========================================================================


class TestPlatformDetector:
    def test_shopify(self):
        html = '<link rel="stylesheet" href="https://cdn.shopify.com/s/files/theme.css">'
        result = platform_detector(html)
        assert result["platform"] == "shopify"
        assert result["platform_detected"] is True

    def test_wordpress(self):
        html = '<link rel="stylesheet" href="/wp-content/themes/custom/style.css">'
        result = platform_detector(html)
        assert result["platform"] == "wordpress"

    def test_toast(self):
        html = '<script src="https://toasttab.com/widget.js"></script>'
        result = platform_detector(html)
        assert result["platform"] == "toast"

    def test_no_platform(self):
        html = "<html><body>Plain site</body></html>"
        result = platform_detector(html)
        assert result["platform"] is None
        assert result["platform_detected"] is False

    def test_empty_html(self):
        result = platform_detector("")
        assert result["platform_detected"] is False

    def test_multiple_platforms(self):
        html = '<link href="/wp-content/style.css"><script src="https://cdn.shopify.com/x.js"></script>'
        result = platform_detector(html)
        assert len(result["platforms_found"]) >= 2

    def test_mindbody(self):
        html = '<script src="https://widgets.mindbodyonline.com/embed.js"></script>'
        result = platform_detector(html)
        assert result["platform"] == "mindbody"

    def test_square_online(self):
        html = '<link href="https://square.site/assets/style.css">'
        result = platform_detector(html)
        assert result["platform"] == "square_online"


# ===========================================================================
# 4. Pixel detector
# ===========================================================================


class TestPixelDetector:
    def test_google_analytics(self):
        html = "<script>gtag('config', 'G-12345');</script>"
        result = pixel_detector(html)
        assert "google_analytics" in result["pixels_found"]
        assert result["has_analytics"] is True

    def test_facebook_pixel(self):
        html = "<script>fbq('init', '123456');</script>"
        result = pixel_detector(html)
        assert "facebook_pixel" in result["pixels_found"]

    def test_multiple_pixels(self):
        html = "<script>gtag('config', 'G-12345');</script><script>fbq('init', '123');</script>"
        result = pixel_detector(html)
        assert result["pixel_count"] >= 2

    def test_no_pixels(self):
        html = "<html><body>No tracking</body></html>"
        result = pixel_detector(html)
        assert result["pixel_count"] == 0
        assert result["has_analytics"] is False

    def test_gtm(self):
        html = '<script src="https://www.googletagmanager.com/gtm.js?id=GTM-ABCDEF"></script>'
        result = pixel_detector(html)
        assert "google_tag_manager" in result["pixels_found"]

    def test_hotjar(self):
        html = '<script src="https://static.hotjar.com/c/hotjar-123.js"></script>'
        result = pixel_detector(html)
        assert "hotjar" in result["pixels_found"]

    def test_tiktok_pixel(self):
        html = '<script src="https://analytics.tiktok.com/i18n/pixel.js"></script>'
        result = pixel_detector(html)
        assert "tiktok_pixel" in result["pixels_found"]


# ===========================================================================
# 5. Contact path detector
# ===========================================================================


class TestContactPathDetector:
    def test_contact_link(self):
        html = '<a href="/contact">Contact Us</a>'
        result = contact_path_detector(html, "https://example.com")
        assert len(result["contact_paths"]) >= 1
        assert result["has_contact_path"] is True

    def test_mailto(self):
        html = '<a href="mailto:info@example.com">Email Us</a>'
        result = contact_path_detector(html)
        assert "info@example.com" in result["mailto_addresses"]
        assert result["has_contact_path"] is True

    def test_tel(self):
        html = '<a href="tel:+12015551234">Call</a>'
        result = contact_path_detector(html)
        assert "+12015551234" in result["tel_numbers"]

    def test_social_links(self):
        html = '<a href="https://instagram.com/shop">IG</a><a href="https://facebook.com/shop">FB</a>'
        result = contact_path_detector(html)
        assert len(result["social_links"]) == 2

    def test_no_contact(self):
        html = "<html><body>No contact info</body></html>"
        result = contact_path_detector(html)
        assert result["has_contact_path"] is False

    def test_about_page(self):
        html = '<a href="/about">About Us</a>'
        result = contact_path_detector(html, "https://example.com")
        assert result["has_contact_path"] is True

    def test_absolute_contact_url(self):
        html = '<a href="https://example.com/contact-us">Contact</a>'
        result = contact_path_detector(html)
        assert "https://example.com/contact-us" in result["contact_paths"]

    def test_multiple_mailto(self):
        html = '<a href="mailto:a@x.com">A</a><a href="mailto:b@x.com">B</a>'
        result = contact_path_detector(html)
        assert len(result["mailto_addresses"]) == 2

    def test_yelp_social_link(self):
        html = '<a href="https://www.yelp.com/biz/test">Yelp</a>'
        result = contact_path_detector(html)
        assert any("yelp.com" in link for link in result["social_links"])


# ===========================================================================
# 6. Meta extractor
# ===========================================================================


class TestMetaExtractor:
    def test_description(self):
        html = '<meta name="description" content="Best pizza in town">'
        result = meta_extractor(html)
        assert result["description"] == "Best pizza in town"

    def test_og_type(self):
        html = '<meta property="og:type" content="restaurant">'
        result = meta_extractor(html)
        assert result["og_type"] == "restaurant"

    def test_jsonld(self):
        html = '<script type="application/ld+json">{"@type": "Restaurant", "name": "Test"}</script>'
        result = meta_extractor(html)
        assert "Restaurant" in result["jsonld_types"]
        assert result["has_structured_data"] is True

    def test_generator(self):
        html = '<meta name="generator" content="WordPress 6.4">'
        result = meta_extractor(html)
        assert "WordPress" in result["generator"]

    def test_title(self):
        html = '<title>Tony\'s Pizza - Best in Town</title>'
        result = meta_extractor(html)
        assert "Tony" in result["title"]

    def test_multiple_jsonld(self):
        html = '''
        <script type="application/ld+json">{"@type": "Restaurant"}</script>
        <script type="application/ld+json">{"@type": "LocalBusiness"}</script>
        '''
        result = meta_extractor(html)
        assert "Restaurant" in result["jsonld_types"]
        assert "LocalBusiness" in result["jsonld_types"]

    def test_empty_html(self):
        result = meta_extractor("")
        assert result["title"] == ""
        assert result["has_structured_data"] is False


# ===========================================================================
# 7. Dynamic threshold
# ===========================================================================


class TestDynamicThreshold:
    def test_default_threshold(self):
        assert compute_dynamic_threshold(None) == 40

    def test_saturated_market(self):
        ctx = {"area_summary": {"competitiveLandscape": {"saturationLevel": "saturated", "existingBusinessCount": 50}}}
        assert compute_dynamic_threshold(ctx) == 60

    def test_underserved_market(self):
        ctx = {"area_summary": {"competitiveLandscape": {"saturationLevel": "low", "existingBusinessCount": 5}}}
        assert compute_dynamic_threshold(ctx) == 30

    def test_high_opportunity_lowers_threshold(self):
        ctx = {"area_summary": {
            "competitiveLandscape": {"saturationLevel": "moderate", "existingBusinessCount": 15},
            "marketOpportunity": {"score": 80},
        }}
        assert compute_dynamic_threshold(ctx) == 30

    def test_underserved_plus_high_opportunity(self):
        ctx = {"area_summary": {
            "competitiveLandscape": {"saturationLevel": "low", "existingBusinessCount": 5},
            "marketOpportunity": {"score": 80},
        }}
        assert compute_dynamic_threshold(ctx) == 20

    def test_threshold_clamped_floor(self):
        ctx = {"area_summary": {
            "competitiveLandscape": {"saturationLevel": "low", "existingBusinessCount": 1},
            "marketOpportunity": {"score": 100},
        }}
        assert compute_dynamic_threshold(ctx) >= 20

    def test_threshold_clamped_ceiling(self):
        ctx = {"area_summary": {"competitiveLandscape": {"saturationLevel": "saturated", "existingBusinessCount": 100}}}
        assert compute_dynamic_threshold(ctx) <= 70

    def test_high_competition(self):
        ctx = {"area_summary": {"competitiveLandscape": {"saturationLevel": "high", "existingBusinessCount": 25}}}
        assert compute_dynamic_threshold(ctx) == 50

    def test_empty_research_context(self):
        assert compute_dynamic_threshold({}) == 40

    def test_missing_competitive_landscape(self):
        ctx = {"area_summary": {"marketOpportunity": {"score": 80}}}
        # No competitive landscape → biz_count=0 < 10 → threshold=30, then -10 for opportunity = 20
        assert compute_dynamic_threshold(ctx) == 20


# ===========================================================================
# 8. Research context extraction
# ===========================================================================


class TestExtractResearchContext:
    def test_area_research(self):
        ctx = extract_research_context(
            area_research={"summary": {"competitiveLandscape": {"saturationLevel": "high"}}},
        )
        assert "area_summary" in ctx

    def test_zipcode_research(self):
        ctx = extract_research_context(
            zipcode_research={"report": {"sections": {"demographics": {"content": "High income area"}}}},
        )
        assert "demographics" in ctx

    def test_sector_research(self):
        ctx = extract_research_context(
            sector_research={"summary": {"industryAnalysis": {"trends": []}}},
        )
        assert "sector_summary" in ctx

    def test_empty_input(self):
        ctx = extract_research_context()
        assert ctx == {}

    def test_all_three(self):
        ctx = extract_research_context(
            area_research={"summary": {"competitiveLandscape": {}}},
            zipcode_research={"report": {"sections": {"demographics": {"content": "test"}}}},
            sector_research={"summary": {"industryAnalysis": {}}},
        )
        assert len(ctx) == 3


# ===========================================================================
# 9. Scoring function
# ===========================================================================


class TestScoring:
    def _make_domain(self, **overrides):
        base = {"domain": "example.com", "domain_type": "custom", "is_custom_domain": True, "is_https": True}
        return {**base, **overrides}

    def _make_empty(self):
        return {
            "platform": None, "platform_detected": False, "platforms_found": [],
            "pixels_found": [], "pixel_count": 0, "has_analytics": False,
            "contact_paths": [], "mailto_addresses": [], "tel_numbers": [],
            "social_links": [], "has_contact_path": False,
            "title": "", "description": "", "og_type": "",
            "generator": "", "jsonld_types": [], "has_structured_data": False,
        }

    def test_custom_domain_score(self):
        score, _ = _score_business(
            "Test Biz", "restaurant", "https://example.com",
            self._make_domain(), self._make_empty(), self._make_empty(),
            self._make_empty(), self._make_empty(), {"status_code": 200},
        )
        assert score >= 15

    def test_innovation_gap_bonus(self):
        platform = {"platform": "toast", "platform_detected": True, "platforms_found": ["toast"]}
        contact = {**self._make_empty(), "social_links": []}
        score, reasons = _score_business(
            "Test Biz", "restaurant", "https://example.com",
            self._make_domain(), platform, self._make_empty(),
            contact, self._make_empty(), {"status_code": 200},
        )
        assert any("Innovation Gap" in r for r in reasons)

    def test_aggregator_escape_bonus(self):
        domain = self._make_domain(is_custom_domain=False, domain_type="platform_subdomain")
        contact = {**self._make_empty(), "social_links": ["https://doordash.com/store/test"]}
        _, reasons = _score_business(
            "Test Biz", "restaurant", "https://test.wixsite.com",
            domain, self._make_empty(), self._make_empty(),
            contact, self._make_empty(), {"status_code": 200},
        )
        assert any("Aggregator Escape" in r for r in reasons)

    def test_services_intake_friction(self):
        contact = {**self._make_empty(), "has_contact_path": False}
        _, reasons = _score_business(
            "Bob's Repair", "auto repair", "https://bobsrepair.com",
            self._make_domain(), self._make_empty(), self._make_empty(),
            contact, self._make_empty(), {"status_code": 200},
        )
        assert any("Services" in r for r in reasons)

    def test_retail_no_ecommerce(self):
        _, reasons = _score_business(
            "Cool Boutique", "retail shop", "https://coolboutique.com",
            self._make_domain(), self._make_empty(), self._make_empty(),
            self._make_empty(), self._make_empty(), {"status_code": 200},
        )
        assert any("Retail" in r for r in reasons)

    def test_economic_delta_bonus(self):
        research = {"demographics": {"content": "Wealthy affluent neighborhood", "key_facts": ["High income area"]}}
        pixels = {**self._make_empty(), "has_analytics": False}
        _, reasons = _score_business(
            "Test", "restaurant", "https://test.com",
            self._make_domain(), self._make_empty(), pixels,
            self._make_empty(), self._make_empty(), {"status_code": 200},
            research_context=research,
        )
        assert any("Economic Delta" in r for r in reasons)

    def test_sector_tech_forward(self):
        platform = {"platform": "shopify", "platform_detected": True, "platforms_found": ["shopify"]}
        research = {"sector_summary": {"industryAnalysis": {"technologyAdoption": [{"name": "Shopify"}]}}}
        _, reasons = _score_business(
            "Test", "retail", "https://test.com",
            self._make_domain(), platform, self._make_empty(),
            self._make_empty(), self._make_empty(), {"status_code": 200},
            research_context=research,
        )
        assert any("tech-forward" in r for r in reasons)

    def test_all_signals_max_score(self):
        """A business with every positive signal should score very high."""
        domain = self._make_domain()
        platform = {"platform": "toast", "platform_detected": True, "platforms_found": ["toast"]}
        pixels = {"pixels_found": ["google_analytics", "facebook_pixel"], "pixel_count": 2, "has_analytics": True}
        contact = {
            "contact_paths": ["/contact"], "mailto_addresses": ["a@b.com"], "tel_numbers": ["+1234"],
            "social_links": ["https://instagram.com/x", "https://facebook.com/x", "https://yelp.com/x"],
            "has_contact_path": True,
        }
        meta = {"title": "Great Biz", "description": "test", "og_type": "restaurant",
                "generator": "", "jsonld_types": ["Restaurant"], "has_structured_data": True}
        score, _ = _score_business(
            "Test", "restaurant", "https://test.com",
            domain, platform, pixels, contact, meta, {"status_code": 200},
        )
        assert score >= 60


# ===========================================================================
# 10. qualify_business (async, mocked HTTP)
# ===========================================================================


class TestQualifyBusiness:
    @pytest.mark.asyncio
    async def test_chain_disqualified(self):
        result = await qualify_business("McDonald's", "https://mcdonalds.com")
        assert result.outcome == DISQUALIFIED

    @pytest.mark.asyncio
    async def test_no_url_parked(self):
        result = await qualify_business("Local Shop", "")
        assert result.outcome == PARKED

    @pytest.mark.asyncio
    async def test_yelp_url_disqualified(self):
        result = await qualify_business("Local Shop", "https://www.yelp.com/biz/local-shop")
        assert result.outcome == DISQUALIFIED

    @pytest.mark.asyncio
    async def test_social_url_disqualified(self):
        result = await qualify_business("Local Shop", "https://www.instagram.com/localshop")
        assert result.outcome == DISQUALIFIED

    @pytest.mark.asyncio
    async def test_strong_site_qualified(self):
        html = """
        <html><head><title>Tony's Pizza</title>
        <script>gtag('config', 'G-12345');</script></head>
        <body><a href="/contact">Contact</a><a href="mailto:info@tonyspizza.com">Email</a>
        <a href="https://instagram.com/tonyspizza">IG</a></body></html>
        """
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 200, "final_url": "https://tonyspizza.com", "error": None}
            result = await qualify_business("Tony's Pizza", "https://tonyspizza.com", "restaurant")
            assert result.outcome == QUALIFIED

    @pytest.mark.asyncio
    async def test_dead_site_disqualified(self):
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": "", "status_code": 404, "final_url": "https://dead.com", "error": None}
            result = await qualify_business("Dead Biz", "https://dead.com")
            assert result.outcome == DISQUALIFIED

    @pytest.mark.asyncio
    async def test_timeout_parked_with_probe(self):
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": "", "status_code": 0, "final_url": "https://slow.com", "error": "timeout"}
            result = await qualify_business("Slow Biz", "https://slow.com")
            assert result.outcome == PARKED
            assert result.needs_full_probe is True

    @pytest.mark.asyncio
    async def test_dynamic_threshold_applied(self):
        html = '<html><head><title>Test</title></head><body><a href="/contact">Contact</a></body></html>'
        research = {"area_summary": {"competitiveLandscape": {"saturationLevel": "saturated", "existingBusinessCount": 50}}}
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 200, "final_url": "https://test.com", "error": None}
            result = await qualify_business("Test Biz", "https://test.com", "restaurant", research_context=research)
            assert result.threshold == 60

    @pytest.mark.asyncio
    async def test_server_error_not_dead(self):
        """500 with HTML content should not disqualify — could be temporary."""
        html = "<html><body>Server error</body></html>"
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 500, "final_url": "https://test.com", "error": None}
            result = await qualify_business("Test Biz", "https://test.com")
            # 500 with HTML → analyzers still run, not instantly disqualified
            assert result.outcome != DISQUALIFIED

    @pytest.mark.asyncio
    async def test_platform_plus_contact_qualifies(self):
        """Rule: platform site + contact path → QUALIFIED regardless of score."""
        html = '<script src="https://cdn.shopify.com/x.js"></script><a href="/contact">Contact</a>'
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 200, "final_url": "https://test.myshopify.com", "error": None}
            result = await qualify_business("Shop", "https://test.myshopify.com")
            assert result.outcome == QUALIFIED

    @pytest.mark.asyncio
    async def test_probe_data_populated(self):
        """Verify probe_data is populated for qualified businesses."""
        html = '<html><head><title>Test</title><script>gtag("config","G-1")</script></head><body><a href="/contact">C</a></body></html>'
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 200, "final_url": "https://test.com", "error": None}
            result = await qualify_business("Test", "https://test.com")
            assert "domain" in result.probe_data
            assert "platform" in result.probe_data
            assert "pixels" in result.probe_data


# ===========================================================================
# 11. LLM classifier
# ===========================================================================


class TestLLMClassifier:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await _run_llm_classifier("Test", "restaurant", {})
            assert result["is_hvt"] is False
            assert "No API key" in result["reason"]

    @pytest.mark.asyncio
    async def test_llm_error_returns_false(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("google.genai.Client") as mock_client:
                mock_client.side_effect = Exception("API error")
                result = await _run_llm_classifier("Test", "restaurant", {"domain": {}})
                assert result["is_hvt"] is False

    @pytest.mark.asyncio
    async def test_llm_success(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            mock_response = MagicMock()
            mock_response.text = '{"is_hvt": true, "reason": "Strong local business"}'
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            with patch("google.genai.Client", return_value=mock_client):
                result = await _run_llm_classifier("Test Biz", "restaurant", {"domain": {"domain_type": "custom"}})
                assert result["is_hvt"] is True


# ===========================================================================
# 12. Full probe
# ===========================================================================


class TestFullProbe:
    @pytest.mark.asyncio
    async def test_probe_upgrades_to_qualified(self):
        """Full probe finding email + social should push score above threshold."""
        partial = QualificationResult(outcome=PARKED, score=35, threshold=40, probe_data={})
        crawl_data = {
            "deterministicContact": {"email": "test@example.com", "phone": "201-555-1234"},
            "socialAnchors": {"instagram": "https://ig.com/test", "facebook": "https://fb.com/test"},
            "deliveryPlatforms": {},
            "jsonLd": {},
        }
        with patch("hephae_agents.shared_tools.playwright.crawl_web_page", new_callable=AsyncMock, return_value=crawl_data):
            result = await _run_full_probe("Test", "https://test.com", "restaurant", partial)
            assert result.outcome == QUALIFIED
            assert result.score >= 40

    @pytest.mark.asyncio
    async def test_probe_preserves_probe_data(self):
        partial = QualificationResult(outcome=PARKED, score=35, threshold=40, probe_data={"domain": {"test": True}})
        crawl_data = {
            "deterministicContact": {"email": "a@b.com"},
            "socialAnchors": {}, "deliveryPlatforms": {}, "jsonLd": {},
        }
        with patch("hephae_agents.shared_tools.playwright.crawl_web_page", new_callable=AsyncMock, return_value=crawl_data):
            result = await _run_full_probe("Test", "https://test.com", "restaurant", partial)
            assert result.probe_data.get("email") == "a@b.com"
            assert result.probe_data.get("domain") == {"test": True}

    @pytest.mark.asyncio
    async def test_probe_crawl_fails_returns_partial(self):
        partial = QualificationResult(outcome=PARKED, score=30, threshold=40, probe_data={})
        with patch("hephae_agents.shared_tools.playwright.crawl_web_page", new_callable=AsyncMock, side_effect=Exception("Browser crash")):
            result = await _run_full_probe("Test", "https://test.com", "restaurant", partial)
            assert result.outcome == PARKED
            assert result.score == 30


# ===========================================================================
# 13. qualify_businesses (batch)
# ===========================================================================


class TestQualifyBusinesses:
    @pytest.mark.asyncio
    async def test_batch_classification(self):
        businesses = [
            {"name": "McDonald's", "url": "https://mcdonalds.com", "category": "restaurant"},
            {"name": "Local Shop", "url": "", "category": "retail"},
            {"name": "Yelp Page", "url": "https://yelp.com/biz/test", "category": "restaurant"},
        ]
        results = await qualify_businesses(businesses, run_full_probe=False)
        assert len(results["disqualified"]) == 2
        assert len(results["parked"]) == 1

    @pytest.mark.asyncio
    async def test_batch_with_qualified(self):
        html = '<html><head><title>Real Biz</title><script>gtag("config","G-12345");</script></head><body><a href="/contact">Contact</a><a href="mailto:info@real.com">Email</a></body></html>'
        businesses = [
            {"name": "Real Business", "url": "https://realbiz.com", "category": "restaurant"},
            {"name": "Subway", "url": "https://subway.com", "category": "restaurant"},
        ]
        with patch("hephae_agents.qualification.scanner.page_fetcher") as mock_fetch:
            mock_fetch.return_value = {"html": html, "status_code": 200, "final_url": "https://realbiz.com", "error": None}
            results = await qualify_businesses(businesses, run_full_probe=False)
            assert len(results["qualified"]) == 1
            assert results["qualified"][0]["name"] == "Real Business"
            assert len(results["disqualified"]) == 1

    @pytest.mark.asyncio
    async def test_batch_error_isolation(self):
        """One business erroring should not crash the batch."""
        businesses = [
            {"name": "McDonald's", "url": "https://mcdonalds.com"},
            {"name": "Good Biz", "url": ""},
        ]
        results = await qualify_businesses(businesses, run_full_probe=False)
        total = len(results["qualified"]) + len(results["parked"]) + len(results["disqualified"])
        assert total == 2

    @pytest.mark.asyncio
    async def test_batch_with_custom_threshold(self):
        businesses = [{"name": "Local", "url": "", "category": "restaurant"}]
        results = await qualify_businesses(businesses, threshold=20, run_full_probe=False)
        assert len(results["parked"]) == 1  # No URL → parked regardless of threshold


# ===========================================================================
# 14. Qualification phase integration
# ===========================================================================


class TestQualificationPhase:
    @pytest.mark.asyncio
    async def test_phase_filters_businesses(self):
        from hephae_common.models import BusinessWorkflowState, BusinessPhase

        businesses = [
            BusinessWorkflowState(slug="mcdonalds", name="McDonald's", officialUrl="https://mcdonalds.com", businessType="restaurant"),
            BusinessWorkflowState(slug="no-url-shop", name="No URL Shop", officialUrl="", businessType="retail"),
        ]

        with patch("hephae_api.workflows.phases.qualification._load_research_context", new_callable=AsyncMock, return_value=None):
            with patch("hephae_common.firebase.get_db") as mock_db:
                mock_db.return_value.collection.return_value.document.return_value.update = MagicMock()

                from hephae_api.workflows.phases.qualification import run_qualification_phase
                results = await run_qualification_phase(
                    businesses, zip_code="07110", business_type="Restaurants",
                )

                assert len(results["disqualified"]) == 1
                assert results["disqualified"][0].slug == "mcdonalds"
                assert len(results["parked"]) == 1

    @pytest.mark.asyncio
    async def test_phase_callbacks_fired(self):
        from hephae_common.models import BusinessWorkflowState

        businesses = [
            BusinessWorkflowState(slug="chain-biz", name="Starbucks", officialUrl="", businessType="cafe"),
        ]

        callback_calls: list[tuple] = []
        done_calls: list[tuple] = []

        with patch("hephae_api.workflows.phases.qualification._load_research_context", new_callable=AsyncMock, return_value=None):
            with patch("hephae_common.firebase.get_db") as mock_db:
                mock_db.return_value.collection.return_value.document.return_value.update = MagicMock()

                from hephae_api.workflows.phases.qualification import run_qualification_phase
                await run_qualification_phase(
                    businesses, zip_code="07110",
                    callbacks={
                        "onBusinessQualified": lambda slug, outcome, score: callback_calls.append((slug, outcome, score)),
                        "onQualificationDone": lambda q, p, d: done_calls.append((q, p, d)),
                    },
                )

                assert len(callback_calls) == 1
                assert callback_calls[0][1] == "DISQUALIFIED"
                assert done_calls[0] == (0, 0, 1)

    @pytest.mark.asyncio
    async def test_multi_zip_research_fallback(self):
        """When first zip has no research, should try subsequent zips."""
        from hephae_common.models import BusinessWorkflowState

        businesses = [
            BusinessWorkflowState(slug="chain", name="Subway", officialUrl="", businessType="restaurant"),
        ]

        call_count = {"n": 0}
        async def mock_load(zip_code, business_type=None):
            call_count["n"] += 1
            if zip_code == "07110":
                return None  # No data for first zip
            return {"area_summary": {"competitiveLandscape": {"saturationLevel": "moderate"}}}

        with patch("hephae_api.workflows.phases.qualification._load_research_context", side_effect=mock_load):
            with patch("hephae_common.firebase.get_db") as mock_db:
                mock_db.return_value.collection.return_value.document.return_value.update = MagicMock()

                from hephae_api.workflows.phases.qualification import run_qualification_phase
                await run_qualification_phase(
                    businesses, zip_code="07110", zip_codes=["07110", "07111"],
                )
                # Should have tried both zips
                assert call_count["n"] == 2


# ===========================================================================
# 15. QualificationResult
# ===========================================================================


class TestQualificationResult:
    def test_to_dict(self):
        result = QualificationResult(
            outcome=QUALIFIED, score=55, threshold=40,
            reasons=["+15: custom domain"],
            probe_data={"domain": {"is_custom_domain": True}},
        )
        d = result.to_dict()
        assert d["outcome"] == "QUALIFIED"
        assert d["score"] == 55
        assert d["threshold"] == 40

    def test_defaults(self):
        result = QualificationResult(outcome=PARKED)
        assert result.score == 0
        assert result.threshold == 40
        assert result.reasons == []
        assert result.probe_data == {}
        assert result.needs_full_probe is False

    def test_needs_full_probe_flag(self):
        result = QualificationResult(outcome=PARKED, needs_full_probe=True)
        d = result.to_dict()
        assert d["needsFullProbe"] is True
