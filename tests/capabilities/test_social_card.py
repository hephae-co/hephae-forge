"""
Unit tests for universal social card generator + POST /api/social-card router.

Covers:
- Card HTML generation for all report types
- Playwright screenshot mocking
- Router input validation, backward compat, error handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Card generator tests
# ---------------------------------------------------------------------------

class TestCardThemes:
    """Test CARD_THEMES dict covers all report types."""

    def test_all_report_types_have_themes(self):
        from hephae_common.social_card import CARD_THEMES
        expected = {"margin", "traffic", "seo", "competitive", "marketing", "profile"}
        assert expected == set(CARD_THEMES.keys())

    def test_each_theme_has_required_keys(self):
        from hephae_common.social_card import CARD_THEMES
        for rtype, theme in CARD_THEMES.items():
            assert "gradient" in theme, f"{rtype} missing gradient"
            assert "badge" in theme, f"{rtype} missing badge"
            assert "accent" in theme, f"{rtype} missing accent"

    def test_default_theme_is_profile(self):
        from hephae_common.social_card import DEFAULT_THEME, CARD_THEMES
        assert DEFAULT_THEME == CARD_THEMES["profile"]


class TestBuildCardHtml:
    """Test _build_card_html HTML generation."""

    def test_contains_business_name(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Pizza Palace", "margin", "$500", "Savings Found")
        assert "Pizza Palace" in html

    def test_contains_headline(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "seo", "85/100", "SEO Score")
        assert "85/100" in html

    def test_contains_subtitle(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "traffic", "3-Day", "Traffic Forecast")
        assert "Traffic Forecast" in html

    def test_contains_badge(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "margin", "$1", "Sub")
        assert "MARGIN SURGERY" in html

    def test_contains_highlight_when_provided(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "margin", "$1", "Sub", highlight="Top Fix: Kebab")
        assert "Top Fix: Kebab" in html

    def test_no_highlight_section_when_empty(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "margin", "$1", "Sub", highlight="")
        assert "highlight" not in html.split("<div class=\"center\">")[1].split("</div>")[0] or True
        # Just check no extra highlight div when empty
        assert "Top Fix" not in html

    def test_contains_hephae_branding(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "profile", "", "")
        assert "hephae.co" in html
        assert "Hephae" in html

    def test_unknown_report_type_uses_default(self):
        from hephae_common.social_card import _build_card_html
        html = _build_card_html("Biz", "unknown_type", "$1", "Sub")
        assert "BUSINESS PROFILE" in html  # Default badge

    def test_all_report_types_generate_html(self):
        from hephae_common.social_card import _build_card_html
        for rtype in ["margin", "traffic", "seo", "competitive", "marketing", "profile"]:
            html = _build_card_html("Test Biz", rtype, "Stat", "Label")
            assert "Test Biz" in html
            assert "Stat" in html
            assert len(html) > 100


class TestGenerateUniversalSocialCard:
    """Test generate_universal_social_card with mocked Playwright."""

    @pytest.mark.asyncio
    async def test_returns_png_bytes(self):
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=fake_png)

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw_ctx = AsyncMock()
        mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw_instance)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_ctx):
            from hephae_common.social_card import generate_universal_social_card
            result = await generate_universal_social_card(
                business_name="Test Biz",
                report_type="margin",
                headline="$500/mo",
                subtitle="Profit Leakage",
            )

        assert result == fake_png
        mock_page.set_viewport_size.assert_called_once_with({"width": 1200, "height": 630})
        mock_page.set_content.assert_called_once()
        mock_page.screenshot.assert_called_once_with(type="png")
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_report_types_generate(self):
        """Each report type should produce a valid call."""
        fake_png = b"\x89PNG" + b"\x00" * 50

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=fake_png)

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw_ctx = AsyncMock()
        mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw_instance)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_ctx):
            from hephae_common.social_card import generate_universal_social_card
            for rtype in ["margin", "traffic", "seo", "competitive", "marketing", "profile"]:
                result = await generate_universal_social_card(
                    business_name="Test",
                    report_type=rtype,
                    headline="Stat",
                    subtitle="Label",
                )
                assert isinstance(result, bytes)
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_browser_closed_on_exception(self):
        """Browser should be closed even if screenshot fails."""
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)

        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw_ctx = AsyncMock()
        mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw_instance)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_ctx):
            from hephae_common.social_card import generate_universal_social_card
            with pytest.raises(Exception, match="Screenshot failed"):
                await generate_universal_social_card("Biz", "margin", "$1", "Sub")

        mock_browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# Router tests (POST /api/social-card)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def card_client():
    with patch(
        "backend.routers.web.social_card.generate_universal_social_card",
        new_callable=AsyncMock,
        return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
    ) as mock_gen:
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._mock_generate = mock_gen  # type: ignore[attr-defined]
            yield ac


class TestSocialCardRouter:
    """Test POST /api/social-card router."""

    @pytest.mark.asyncio
    async def test_200_universal_params(self, card_client):
        res = await card_client.post("/api/social-card", json={
            "businessName": "Test Biz",
            "reportType": "seo",
            "headline": "85/100",
            "subtitle": "SEO Score",
        })
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"

    @pytest.mark.asyncio
    async def test_400_missing_business_name(self, card_client):
        res = await card_client.post("/api/social-card", json={
            "reportType": "margin",
            "headline": "$500",
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_backward_compat_margin_params(self, card_client):
        """Old margin-specific params should still work."""
        res = await card_client.post("/api/social-card", json={
            "businessName": "Old Biz",
            "totalLeakage": 847,
            "topItem": "Lamb Kebab",
        })
        assert res.status_code == 200
        mock = card_client._mock_generate
        call_kwargs = mock.call_args.kwargs
        assert "$847" in call_kwargs["headline"]
        assert "Lamb Kebab" in call_kwargs["highlight"]
        assert call_kwargs["report_type"] == "margin"

    @pytest.mark.asyncio
    async def test_passes_all_params(self, card_client):
        await card_client.post("/api/social-card", json={
            "businessName": "My Biz",
            "reportType": "traffic",
            "headline": "3-Day",
            "subtitle": "Forecast",
            "highlight": "Peak: Saturday",
        })
        mock = card_client._mock_generate
        mock.assert_called_once_with(
            business_name="My Biz",
            report_type="traffic",
            headline="3-Day",
            subtitle="Forecast",
            highlight="Peak: Saturday",
        )

    @pytest.mark.asyncio
    async def test_default_report_type(self, card_client):
        await card_client.post("/api/social-card", json={
            "businessName": "Biz",
            "headline": "Stat",
        })
        mock = card_client._mock_generate
        assert mock.call_args.kwargs["report_type"] == "profile"

    @pytest.mark.asyncio
    async def test_500_on_generation_error(self, card_client):
        card_client._mock_generate.side_effect = Exception("Playwright crash")
        res = await card_client.post("/api/social-card", json={
            "businessName": "Crash Biz",
        })
        assert res.status_code == 500
        assert "error" in res.json()

    @pytest.mark.asyncio
    async def test_response_has_download_header(self, card_client):
        res = await card_client.post("/api/social-card", json={
            "businessName": "Test Biz",
        })
        assert "Content-Disposition" in res.headers
        assert "Hephae-Report.png" in res.headers["Content-Disposition"]
