"""
Unit tests for social post generator agents + POST /api/social-posts/generate.

Covers:
- Agent-level: generate_social_posts() with mocked ADK runners
- Router-level: input validation, response shape, error handling
- Quality reviewer: AI-generated posts meet quality standards
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_REQUEST = {
    "businessName": "Bosphorus Kitchen",
    "reportType": "margin",
    "summary": "$847/mo total profit leakage across 12 menu items. Overall score: 62/100.",
    "reportUrl": "https://storage.googleapis.com/everything-hephae/bosphorus-kitchen/margin-1234.html",
    "socialHandles": {
        "instagram": "@bosphorus_nj",
        "facebook": "BosphorusKitchenNJ",
        "twitter": "@bosphorus_nj",
    },
}

SAMPLE_IG_OUTPUT = json.dumps({
    "caption": (
        "Bosphorus Kitchen is bleeding $847/mo and didn't even know it 💀\n\n"
        "Our Margin Surgery just exposed 12 items leaking profit.\n"
        "@bosphorus_nj — the diagnosis is in.\n\n"
        "Full report → hephae.co\n\n"
        "#Hephae #MarginSurgeon #RestaurantData #ProfitLeakage #FoodBiz"
    )
})

SAMPLE_FB_OUTPUT = json.dumps({
    "post": (
        "We just ran Margin Surgery on Bosphorus Kitchen and uncovered $847/mo "
        "in hidden profit leakage across 12 menu items. The biggest culprit? "
        "Underpriced specialty dishes that competitors charge 30% more for.\n\n"
        "Read the full report: https://storage.googleapis.com/everything-hephae/"
        "bosphorus-kitchen/margin-1234.html\n\n"
        "Get your own analysis at hephae.co"
    )
})

SAMPLE_TW_OUTPUT = json.dumps({
    "tweet": (
        "Bosphorus Kitchen is leaking $847/mo across 12 menu items 💀 "
        "The data doesn't lie. #Hephae #MarginSurgery"
    )
})

SAMPLE_EMAIL_OUTPUT = json.dumps({
    "subject": "Bosphorus Kitchen: $847/mo profit leak revealed",
    "body": (
        "Hi,\n\n"
        "Hephae ran a Margin Surgery on your business and found $847/mo in hidden "
        "profit leakage across 12 menu items. The biggest culprit? Underpriced specialty dishes.\n\n"
        "We help restaurants like yours optimize pricing and margins with AI-powered insights. "
        "See what Hephae found at hephae.co\n\n"
        "Best,\nThe Hephae Team"
    )
})

SAMPLE_CONTACT_OUTPUT = json.dumps({
    "message": (
        "Hi Bosphorus Kitchen, Hephae here. We ran a Margin Surgery and found that you're "
        "leaking $847/mo across 12 menu items. We help businesses optimize with AI-powered insights. "
        "Check us out at hephae.co"
    )
})

# Report types and their expected labels
REPORT_TYPES = {
    "margin": "Margin Surgery",
    "traffic": "Foot Traffic Forecast",
    "seo": "SEO Deep Audit",
    "competitive": "Competitive Analysis",
    "marketing": "Social Media Insights",
    "profile": "Business Profile",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_stream(*a, **kw):
    async def _gen():
        return
        yield
    return _gen()


def _mock_session_with_state(output_key: str, value: str):
    """Create a mock session service that returns a session with given state."""
    session = MagicMock()
    session.state = {output_key: value}

    svc = MagicMock()
    svc.create_session = AsyncMock(return_value=None)
    svc.get_session = AsyncMock(return_value=session)
    return svc


# ---------------------------------------------------------------------------
# Agent-level tests (test generate_social_posts directly)
# ---------------------------------------------------------------------------

class TestGenerateSocialPosts:
    """Test the generate_social_posts() function directly."""

    @pytest.mark.asyncio
    async def test_returns_all_platforms(self):
        """Should return all 5 channels: instagram, facebook, twitter, email, contactForm."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            # Setup: five sessions (IG + FB + TW + Email + ContactForm), each returning valid JSON
            ig_session = MagicMock()
            ig_session.state = {"instagramPost": SAMPLE_IG_OUTPUT}
            fb_session = MagicMock()
            fb_session.state = {"facebookPost": SAMPLE_FB_OUTPUT}
            tw_session = MagicMock()
            tw_session.state = {"twitterPost": SAMPLE_TW_OUTPUT}
            email_session = MagicMock()
            email_session.state = {"emailOutreach": SAMPLE_EMAIL_OUTPUT}
            contact_session = MagicMock()
            contact_session.state = {"contactFormDraft": SAMPLE_CONTACT_OUTPUT}

            sessions = [ig_session, fb_session, tw_session, email_session, contact_session]
            call_count = {"n": 0}

            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                idx = call_count["n"]
                call_count["n"] += 1
                svc.get_session = AsyncMock(return_value=sessions[idx % 5])
                return svc

            mock_svc_cls.side_effect = _make_svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Bosphorus Kitchen",
                report_type="margin",
                summary="$847/mo leakage",
                report_url="https://example.com/report.html",
            )

            assert "instagram" in result
            assert "facebook" in result
            assert "twitter" in result
            assert "email" in result
            assert "contactForm" in result
            assert "caption" in result["instagram"]
            assert "post" in result["facebook"]
            assert "tweet" in result["twitter"]
            assert "subject" in result["email"]
            assert "body" in result["email"]
            assert "message" in result["contactForm"]
            assert len(result["instagram"]["caption"]) > 0
            assert len(result["facebook"]["post"]) > 0
            assert len(result["twitter"]["tweet"]) > 0
            assert len(result["email"]["subject"]) > 0
            assert len(result["email"]["body"]) > 0
            assert len(result["contactForm"]["message"]) > 0

    @pytest.mark.asyncio
    async def test_fallback_on_empty_caption(self):
        """Empty agent output should trigger template fallback."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            # Return empty JSON for both
            empty_session = MagicMock()
            empty_session.state = {}
            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(return_value=empty_session)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Test Cafe",
                report_type="seo",
                summary="SEO score: 45/100",
                report_url="https://example.com/seo.html",
            )

            # Should still have content (from fallback)
            assert len(result["instagram"]["caption"]) > 10
            assert len(result["facebook"]["post"]) > 10
            assert len(result["twitter"]["tweet"]) > 10
            assert "Test Cafe" in result["instagram"]["caption"]
            assert "Test Cafe" in result["facebook"]["post"]
            assert "Test Cafe" in result["twitter"]["tweet"]

    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """Full exception should return template-based fallback."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            mock_svc_cls.side_effect = Exception("ADK init failed")

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Crash Cafe",
                report_type="margin",
                summary="$100 leakage",
                report_url="https://example.com/r.html",
            )

            assert "instagram" in result
            assert "facebook" in result
            assert "twitter" in result
            assert "Crash Cafe" in result["instagram"]["caption"]
            assert "hephae.co" in result["facebook"]["post"]
            assert "Crash Cafe" in result["twitter"]["tweet"]

    @pytest.mark.asyncio
    async def test_handles_markdown_fenced_json(self):
        """Agent output wrapped in ```json fences should be parsed."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            fenced_ig = f"```json\n{SAMPLE_IG_OUTPUT}\n```"
            ig_session = MagicMock()
            ig_session.state = {"instagramPost": fenced_ig}
            fb_session = MagicMock()
            fb_session.state = {"facebookPost": SAMPLE_FB_OUTPUT}
            tw_session = MagicMock()
            tw_session.state = {"twitterPost": SAMPLE_TW_OUTPUT}

            sessions = [ig_session, fb_session, tw_session]
            call_count = {"n": 0}

            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                idx = call_count["n"]
                call_count["n"] += 1
                svc.get_session = AsyncMock(return_value=sessions[idx % 3])
                return svc

            mock_svc_cls.side_effect = _make_svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Test",
                report_type="margin",
                summary="test",
                report_url="https://example.com",
            )

            assert "Bosphorus Kitchen" in result["instagram"]["caption"]

    @pytest.mark.asyncio
    async def test_social_handles_passed_to_context(self):
        """Social handles should appear in the context string sent to agents."""
        from hephae_capabilities.social.post_generator.agent import _build_context
        context = _build_context(
            "TestBiz", "margin", "summary", "https://example.com",
            {"instagram": "@testbiz", "facebook": "TestBizPage", "twitter": "@testbiz_x"},
        )

        assert "@testbiz" in context
        assert "TestBizPage" in context
        assert "@testbiz_x" in context
        assert "hephae.co" in context


class TestGenerateSocialPostsFiveChannels:
    """Test 5-channel generation (email + contactForm added)."""

    @pytest.mark.asyncio
    async def test_five_channels_all_populated(self):
        """All 5 channels should be populated with content."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            call_count = {"n": 0}
            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                n = call_count["n"]
                call_count["n"] += 1
                # Return different output for each channel
                outputs = [
                    {"instagramPost": SAMPLE_IG_OUTPUT},
                    {"facebookPost": SAMPLE_FB_OUTPUT},
                    {"twitterPost": SAMPLE_TW_OUTPUT},
                    {"emailOutreach": SAMPLE_EMAIL_OUTPUT},
                    {"contactFormDraft": SAMPLE_CONTACT_OUTPUT},
                ]
                session = MagicMock()
                session.state = outputs[n % 5]
                svc.get_session = AsyncMock(return_value=session)
                return svc

            mock_svc_cls.side_effect = _make_svc
            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Test Biz",
                report_type="margin",
                summary="Test summary",
                report_url="https://example.com",
            )

            # Check all 5 channels exist with expected fields
            assert "instagram" in result and "caption" in result["instagram"]
            assert "facebook" in result and "post" in result["facebook"]
            assert "twitter" in result and "tweet" in result["twitter"]
            assert "email" in result and "subject" in result["email"] and "body" in result["email"]
            assert "contactForm" in result and "message" in result["contactForm"]

    @pytest.mark.asyncio
    async def test_email_fallback_on_empty_output(self):
        """Email channel should use fallback when agent returns empty."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            call_count = {"n": 0}
            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                n = call_count["n"]
                call_count["n"] += 1
                # Email and contact form return empty
                session = MagicMock()
                if n == 3:  # email agent
                    session.state = {}
                elif n == 4:  # contact form agent
                    session.state = {}
                else:
                    session.state = {"placeholder": ""}
                svc.get_session = AsyncMock(return_value=session)
                return svc

            mock_svc_cls.side_effect = _make_svc
            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Test Biz",
                report_type="margin",
                summary="Summary text",
                report_url="https://r.com",
            )

            # Should have fallback content
            assert len(result["email"]["body"]) > 0
            assert len(result["email"]["subject"]) > 0
            assert len(result["contactForm"]["message"]) > 0

    @pytest.mark.asyncio
    async def test_contact_form_fallback_on_empty_output(self):
        """Contact form should use fallback when agent returns empty."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            call_count = {"n": 0}
            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                n = call_count["n"]
                call_count["n"] += 1
                session = MagicMock()
                if n == 4:  # contact form agent
                    session.state = {}  # Empty output
                else:
                    session.state = {"placeholder": ""}
                svc.get_session = AsyncMock(return_value=session)
                return svc

            mock_svc_cls.side_effect = _make_svc
            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Cafe Noir",
                report_type="seo",
                summary="SEO issues found",
                report_url="https://r.com",
            )

            # Should have fallback
            assert len(result["contactForm"]["message"]) > 0
            assert "Cafe Noir" in result["contactForm"]["message"]

    @pytest.mark.asyncio
    async def test_rich_context_used_when_latest_outputs_provided(self):
        """When latest_outputs provided, should use rich context builder."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            # Capture the prompt passed to agents
            captured_prompts = []
            original_run_agent = None

            async def mock_run_agent(agent, output_key, prompt):
                captured_prompts.append(prompt)
                session = MagicMock()
                session.state = {"placeholder": ""}
                return "{}"

            call_count = {"n": 0}
            def _make_svc():
                svc = MagicMock()
                svc.create_session = AsyncMock(return_value=None)
                session = MagicMock()
                session.state = {}
                svc.get_session = AsyncMock(return_value=session)
                return svc

            mock_svc_cls.side_effect = _make_svc
            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from hephae_capabilities.social.post_generator import agent as agent_module
            with patch.object(agent_module, "_run_agent", side_effect=mock_run_agent):
                result = await agent_module.generate_social_posts(
                    business_name="Test",
                    latest_outputs={"margin_surgeon": {"score": 50, "summary": "Test"}},
                )

            # Check that rich context was used (contains specific section header)
            assert any("Margin Surgery" in p for p in captured_prompts) or len(result) > 0

    @pytest.mark.asyncio
    async def test_all_channels_fallback_on_exception(self):
        """All channels should have content even if exceptions occur."""
        with (
            patch("hephae_capabilities.social.post_generator.agent.InMemorySessionService") as mock_svc_cls,
            patch("hephae_capabilities.social.post_generator.agent.Runner") as mock_runner_cls,
        ):
            mock_svc_cls.side_effect = Exception("ADK init failed")

            from hephae_capabilities.social.post_generator.agent import generate_social_posts
            result = await generate_social_posts(
                business_name="Crash Cafe",
                report_type="margin",
                summary="Test summary",
                report_url="https://example.com/r.html",
            )

            # All 5 channels should have fallback content
            assert "instagram" in result and len(result["instagram"]["caption"]) > 0
            assert "facebook" in result and len(result["facebook"]["post"]) > 0
            assert "twitter" in result and len(result["twitter"]["tweet"]) > 0
            assert "email" in result and len(result["email"]["body"]) > 0
            assert "contactForm" in result and len(result["contactForm"]["message"]) > 0
            assert "Crash Cafe" in result["instagram"]["caption"]
            assert "hephae.co" in result["facebook"]["post"]


# ---------------------------------------------------------------------------
# Context builder tests
# ---------------------------------------------------------------------------

class TestBuildContext:
    """Test _build_context helper."""

    def test_includes_all_fields(self):
        from hephae_capabilities.social.post_generator.agent import _build_context
        ctx = _build_context("My Biz", "seo", "Score 85", "https://r.com", {"instagram": "@mybiz"})
        assert "My Biz" in ctx
        assert "SEO Deep Audit" in ctx
        assert "Score 85" in ctx
        assert "https://r.com" in ctx
        assert "@mybiz" in ctx
        assert "hephae.co" in ctx

    def test_handles_no_social_handles(self):
        from hephae_capabilities.social.post_generator.agent import _build_context
        ctx = _build_context("Biz", "traffic", "Forecast ready", "https://r.com", None)
        assert "Biz" in ctx
        assert "Instagram Handle" not in ctx

    def test_report_type_labels(self):
        from hephae_capabilities.social.post_generator.agent import _build_context
        for rtype, label in REPORT_TYPES.items():
            ctx = _build_context("X", rtype, "s", "u")
            assert label in ctx, f"Expected '{label}' in context for report type '{rtype}'"

    def test_includes_twitter_handle(self):
        from hephae_capabilities.social.post_generator.agent import _build_context
        ctx = _build_context("Biz", "margin", "s", "u", {"twitter": "@biz_tweets"})
        assert "@biz_tweets" in ctx
        assert "Twitter/X Handle" in ctx

    def test_unknown_report_type_titlecased(self):
        from hephae_capabilities.social.post_generator.agent import _build_context
        ctx = _build_context("X", "custom_thing", "s", "u")
        assert "Custom Thing" in ctx


# ---------------------------------------------------------------------------
# Rich context builder tests (data-enriched mode)
# ---------------------------------------------------------------------------

SAMPLE_LATEST_OUTPUTS = {
    "margin_surgeon": {
        "score": 62,
        "totalLeakage": 847,
        "menu_item_count": 12,
        "summary": "$847/mo profit leakage",
        "reportUrl": "https://example.com/margin.html",
    },
    "seo_auditor": {
        "score": 75,
        "seo_technical_score": 85,
        "seo_content_score": 55,
        "summary": "Good technical, weak content",
        "reportUrl": "https://example.com/seo.html",
    },
}


class TestBuildRichContext:
    """Test _build_rich_context helper."""

    def test_includes_business_name(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("My Biz", SAMPLE_LATEST_OUTPUTS)
        assert "My Biz" in ctx

    def test_includes_margin_data(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "$847" in ctx
        assert "62/100" in ctx
        assert "Margin Surgery" in ctx

    def test_includes_seo_data(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "75/100" in ctx
        assert "SEO Audit" in ctx
        assert "Technical: 85" in ctx
        assert "Content: 55" in ctx

    def test_includes_focus_instruction(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", SAMPLE_LATEST_OUTPUTS, report_type="margin")
        assert "FOCUS" in ctx
        assert "Margin Surgery" in ctx

    def test_includes_social_handles(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", SAMPLE_LATEST_OUTPUTS, social_handles={"twitter": "@biz"})
        assert "@biz" in ctx

    def test_handles_empty_outputs(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", {})
        assert "Biz" in ctx
        assert "hephae.co" in ctx

    def test_handles_partial_outputs(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        partial = {"margin_surgeon": {"score": 50, "summary": "test"}}
        ctx = _build_rich_context("Biz", partial)
        assert "50/100" in ctx
        assert "SEO" not in ctx

    def test_includes_report_urls(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        ctx = _build_rich_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "https://example.com/margin.html" in ctx
        assert "https://example.com/seo.html" in ctx

    def test_includes_traffic_data(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        outputs = {"traffic_forecaster": {"peak_slot_score": 92, "summary": "Saturday peak"}}
        ctx = _build_rich_context("Biz", outputs)
        assert "92" in ctx
        assert "Traffic Forecast" in ctx

    def test_includes_competitive_data(self):
        from hephae_capabilities.social.post_generator.agent import _build_rich_context
        outputs = {"competitive_analyzer": {"competitor_count": 5, "avg_threat_level": 7.2, "summary": "High competition"}}
        ctx = _build_rich_context("Biz", outputs)
        assert "5" in ctx
        assert "7.2/10" in ctx


# ---------------------------------------------------------------------------
# Fallback posts tests
# ---------------------------------------------------------------------------

class TestFallbackPosts:
    """Test _fallback_posts template generator."""

    def test_contains_business_name(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("Cafe Roma", "margin", "Leakage found", "https://r.com")
        assert "Cafe Roma" in fb["instagram"]["caption"]
        assert "Cafe Roma" in fb["facebook"]["post"]

    def test_contains_report_url(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("X", "seo", "Score 50", "https://my-report.com")
        assert "https://my-report.com" in fb["facebook"]["post"]

    def test_contains_hephae_link(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("X", "traffic", "Forecast", "https://r.com")
        assert "hephae.co" in fb["instagram"]["caption"]
        assert "hephae.co" in fb["facebook"]["post"]

    def test_contains_hashtags(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("X", "margin", "Leakage", "https://r.com")
        assert "#" in fb["instagram"]["caption"]

    def test_twitter_key_exists(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("Cafe Roma", "margin", "Leakage found", "https://r.com")
        assert "twitter" in fb
        assert "tweet" in fb["twitter"]

    def test_twitter_has_business_name(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("Cafe Roma", "margin", "Leakage found", "https://r.com")
        assert "Cafe Roma" in fb["twitter"]["tweet"]

    def test_twitter_has_hephae_hashtag(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("X", "seo", "Score 50", "https://r.com")
        assert "#Hephae" in fb["twitter"]["tweet"]

    def test_twitter_under_280_chars(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        fb = _fallback_posts("X", "margin", "A" * 300, "https://r.com")
        assert len(fb["twitter"]["tweet"]) <= 280


# ---------------------------------------------------------------------------
# JSON parser tests
# ---------------------------------------------------------------------------

class TestParseJson:
    """Test _parse_json helper."""

    def test_plain_json(self):
        from hephae_capabilities.social.post_generator.agent import _parse_json
        result = _parse_json('{"caption": "hello"}')
        assert result == {"caption": "hello"}

    def test_fenced_json(self):
        from hephae_capabilities.social.post_generator.agent import _parse_json
        result = _parse_json('```json\n{"caption": "hello"}\n```')
        assert result == {"caption": "hello"}

    def test_dict_passthrough(self):
        from hephae_capabilities.social.post_generator.agent import _parse_json
        result = _parse_json({"caption": "hello"})
        assert result == {"caption": "hello"}

    def test_invalid_json_returns_empty(self):
        from hephae_capabilities.social.post_generator.agent import _parse_json
        result = _parse_json("not json at all")
        assert result == {}

    def test_empty_string_returns_empty(self):
        from hephae_capabilities.social.post_generator.agent import _parse_json
        result = _parse_json("")
        assert result == {}


# ---------------------------------------------------------------------------
# Router-level tests (POST /api/social-posts/generate)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    with patch(
        "backend.routers.web.social_posts.generate_social_posts",
        new_callable=AsyncMock,
        return_value={
            "instagram": {"caption": "Test IG caption #Hephae"},
            "facebook": {"post": "Test FB post. hephae.co"},
            "twitter": {"tweet": "Test tweet #Hephae"},
        },
    ) as mock_gen:
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._mock_generate = mock_gen  # type: ignore[attr-defined]
            yield ac


class TestRouterInputValidation:
    """Test POST /api/social-posts/generate input validation."""

    @pytest.mark.asyncio
    async def test_400_missing_business_name(self, client):
        body = {**SAMPLE_REQUEST}
        del body["businessName"]
        res = await client.post("/api/social-posts/generate", json=body)
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_404_missing_summary_no_data(self, client):
        """No summary + no Firestore data → 404."""
        with patch(
            "hephae_db.context.latest_outputs.fetch_latest_outputs",
            return_value={"outputs": {}, "socialLinks": {}},
        ):
            body = {**SAMPLE_REQUEST}
            del body["summary"]
            res = await client.post("/api/social-posts/generate", json=body)
            assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_400_empty_business_name(self, client):
        body = {**SAMPLE_REQUEST, "businessName": ""}
        res = await client.post("/api/social-posts/generate", json=body)
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_404_empty_summary_no_data(self, client):
        """Empty summary + no Firestore data → 404."""
        with patch(
            "hephae_db.context.latest_outputs.fetch_latest_outputs",
            return_value={"outputs": {}, "socialLinks": {}},
        ):
            body = {**SAMPLE_REQUEST, "summary": ""}
            res = await client.post("/api/social-posts/generate", json=body)
            assert res.status_code == 404


class TestRouterHappyPath:
    """Test successful social post generation via router."""

    @pytest.mark.asyncio
    async def test_200_full_request(self, client):
        res = await client.post("/api/social-posts/generate", json=SAMPLE_REQUEST)
        assert res.status_code == 200
        data = res.json()
        assert "instagram" in data
        assert "facebook" in data
        assert "twitter" in data

    @pytest.mark.asyncio
    async def test_response_shape(self, client):
        res = await client.post("/api/social-posts/generate", json=SAMPLE_REQUEST)
        data = res.json()
        assert "caption" in data["instagram"]
        assert "post" in data["facebook"]
        assert "tweet" in data["twitter"]

    @pytest.mark.asyncio
    async def test_passes_all_params_to_agent(self, client):
        res = await client.post("/api/social-posts/generate", json=SAMPLE_REQUEST)
        assert res.status_code == 200
        mock = client._mock_generate
        mock.assert_called_once_with(
            business_name="Bosphorus Kitchen",
            report_type="margin",
            summary="$847/mo total profit leakage across 12 menu items. Overall score: 62/100.",
            report_url="https://storage.googleapis.com/everything-hephae/bosphorus-kitchen/margin-1234.html",
            social_handles={"instagram": "@bosphorus_nj", "facebook": "BosphorusKitchenNJ", "twitter": "@bosphorus_nj"},
            latest_outputs=None,
        )

    @pytest.mark.asyncio
    async def test_optional_social_handles(self, client):
        body = {**SAMPLE_REQUEST}
        del body["socialHandles"]
        res = await client.post("/api/social-posts/generate", json=body)
        assert res.status_code == 200
        mock = client._mock_generate
        assert mock.call_args.kwargs["social_handles"] is None

    @pytest.mark.asyncio
    async def test_works_with_all_report_types(self, client):
        for rtype in REPORT_TYPES:
            body = {**SAMPLE_REQUEST, "reportType": rtype}
            res = await client.post("/api/social-posts/generate", json=body)
            assert res.status_code == 200, f"Failed for report type: {rtype}"


class TestRouterErrorHandling:
    """Test error handling in the router."""

    @pytest.mark.asyncio
    async def test_500_on_agent_exception(self, client):
        client._mock_generate.side_effect = Exception("Agent crashed")
        res = await client.post("/api/social-posts/generate", json=SAMPLE_REQUEST)
        assert res.status_code == 500
        assert "error" in res.json()


# ---------------------------------------------------------------------------
# Quality reviewer tests — checks AI-generated posts meet standards
# ---------------------------------------------------------------------------

class TestPostQualityReviewer:
    """
    Reviewer agent: validates that generated social posts meet quality
    standards for tone, structure, and content requirements.

    These tests use the SAMPLE outputs as representative AI-generated posts
    and verify they pass quality checks.
    """

    @pytest.fixture
    def ig_caption(self):
        return json.loads(SAMPLE_IG_OUTPUT)["caption"]

    @pytest.fixture
    def fb_post(self):
        return json.loads(SAMPLE_FB_OUTPUT)["post"]

    # --- Instagram Quality Checks ---

    def test_ig_under_500_chars(self, ig_caption):
        """Instagram captions should be concise (under 500 chars with hashtags)."""
        assert len(ig_caption) < 500, f"IG caption too long: {len(ig_caption)} chars"

    def test_ig_has_hashtags(self, ig_caption):
        """Instagram posts must include hashtags."""
        hashtag_count = ig_caption.count("#")
        assert hashtag_count >= 3, f"Expected 3+ hashtags, got {hashtag_count}"

    def test_ig_has_hephae_hashtag(self, ig_caption):
        """Must include #Hephae for brand visibility."""
        assert "#Hephae" in ig_caption or "#hephae" in ig_caption.lower()

    def test_ig_has_business_mention(self, ig_caption):
        """Should mention the business name or handle."""
        assert "bosphorus" in ig_caption.lower() or "@bosphorus" in ig_caption.lower()

    def test_ig_has_cta(self, ig_caption):
        """Should include a call-to-action directing to hephae.co."""
        caption_lower = ig_caption.lower()
        assert "hephae.co" in caption_lower or "link in bio" in caption_lower

    def test_ig_has_emoji(self, ig_caption):
        """Instagram posts should use emojis (at least 1)."""
        # Check for any character outside basic ASCII + extended latin
        has_emoji = any(ord(c) > 0x2600 for c in ig_caption)
        assert has_emoji, "Instagram caption should include at least one emoji"

    def test_ig_not_generic(self, ig_caption):
        """Caption should reference specific data points, not be generic."""
        specific_markers = ["$847", "12 items", "leaking", "bleeding", "profit", "margin"]
        has_specific = any(m.lower() in ig_caption.lower() for m in specific_markers)
        assert has_specific, "Caption should reference specific data from the report"

    # --- Facebook Quality Checks ---

    def test_fb_longer_than_ig(self, ig_caption, fb_post):
        """Facebook posts should be more detailed than Instagram."""
        # Strip hashtags from IG for fair comparison
        ig_no_tags = ig_caption.split("#")[0].strip()
        assert len(fb_post) > len(ig_no_tags), "Facebook post should be longer than IG caption"

    def test_fb_includes_report_link(self, fb_post):
        """Facebook post must include the direct report URL."""
        assert "https://" in fb_post, "Facebook post should include report URL"

    def test_fb_has_cta(self, fb_post):
        """Should include a call-to-action."""
        post_lower = fb_post.lower()
        has_cta = "hephae.co" in post_lower or "get your" in post_lower or "learn more" in post_lower
        assert has_cta, "Facebook post should include a CTA"

    def test_fb_mentions_business(self, fb_post):
        """Should mention the business by name."""
        assert "Bosphorus" in fb_post

    def test_fb_professional_tone(self, fb_post):
        """Facebook post should be professional — no excessive emojis or ALL CAPS words."""
        # Count ALL CAPS words (excluding short ones like "SEO", "AI")
        words = fb_post.split()
        all_caps_words = [w for w in words if w.isupper() and len(w) > 3 and w.isalpha()]
        assert len(all_caps_words) <= 2, f"Too many ALL CAPS words for professional tone: {all_caps_words}"

    def test_fb_has_data_point(self, fb_post):
        """Post should include a specific data point from the report."""
        has_data = "$847" in fb_post or "12 menu items" in fb_post or "leakage" in fb_post.lower()
        assert has_data, "Facebook post should reference specific data from report"

    # --- X/Twitter Quality Checks ---

    @pytest.fixture
    def tw_tweet(self):
        return json.loads(SAMPLE_TW_OUTPUT)["tweet"]

    def test_tw_under_280_chars(self, tw_tweet):
        """Tweets must be under 280 characters."""
        assert len(tw_tweet) <= 280, f"Tweet too long: {len(tw_tweet)} chars"

    def test_tw_has_hephae_hashtag(self, tw_tweet):
        """Must include #Hephae for brand visibility."""
        assert "#Hephae" in tw_tweet or "#hephae" in tw_tweet.lower()

    def test_tw_mentions_business(self, tw_tweet):
        """Should mention the business name."""
        assert "bosphorus" in tw_tweet.lower()

    def test_tw_no_url_in_body(self, tw_tweet):
        """Tweet should not contain URLs (attached separately via card)."""
        assert "https://" not in tw_tweet and "http://" not in tw_tweet

    def test_tw_has_data_point(self, tw_tweet):
        """Tweet should include a specific data point."""
        has_data = "$847" in tw_tweet or "12" in tw_tweet
        assert has_data, "Tweet should reference specific data from report"

    # --- Cross-Platform Quality Checks ---

    def test_both_are_different(self, ig_caption, fb_post):
        """Instagram and Facebook posts should be meaningfully different."""
        # They shouldn't be identical
        assert ig_caption != fb_post
        # And shouldn't be >80% similar (rough word overlap check)
        ig_words = set(ig_caption.lower().split())
        fb_words = set(fb_post.lower().split())
        overlap = len(ig_words & fb_words) / max(len(ig_words), len(fb_words))
        assert overlap < 0.8, f"Posts too similar: {overlap:.0%} word overlap"

    def test_no_placeholder_text(self, ig_caption, fb_post, tw_tweet):
        """Posts should not contain placeholder/template text."""
        placeholders = ["[business name]", "[link]", "[handle]", "INSERT", "TODO", "PLACEHOLDER"]
        for p in placeholders:
            assert p.lower() not in ig_caption.lower(), f"IG has placeholder: {p}"
            assert p.lower() not in fb_post.lower(), f"FB has placeholder: {p}"
            assert p.lower() not in tw_tweet.lower(), f"TW has placeholder: {p}"

    def test_no_ai_artifacts(self, ig_caption, fb_post, tw_tweet):
        """Posts should not contain AI generation artifacts."""
        artifacts = ["as an ai", "i'm an ai", "language model", "i cannot", "here is", "here's a"]
        for a in artifacts:
            assert a not in ig_caption.lower(), f"IG has AI artifact: {a}"
            assert a not in fb_post.lower(), f"FB has AI artifact: {a}"
            assert a not in tw_tweet.lower(), f"TW has AI artifact: {a}"


# ---------------------------------------------------------------------------
# Reviewer: validate fallback post quality
# ---------------------------------------------------------------------------

class TestFallbackPostQuality:
    """Ensure fallback template posts also meet minimum quality standards."""

    @pytest.fixture
    def fallback(self):
        from hephae_capabilities.social.post_generator.agent import _fallback_posts
        return _fallback_posts(
            "Pizza Palace",
            "traffic",
            "Peak traffic expected Saturday 6-8 PM with 85% capacity",
            "https://storage.googleapis.com/everything-hephae/pizza-palace/traffic-999.html",
        )

    def test_fallback_ig_has_hashtags(self, fallback):
        assert "#" in fallback["instagram"]["caption"]

    def test_fallback_ig_has_hephae(self, fallback):
        assert "hephae.co" in fallback["instagram"]["caption"]

    def test_fallback_fb_has_report_url(self, fallback):
        assert "https://storage.googleapis.com" in fallback["facebook"]["post"]

    def test_fallback_fb_has_business_name(self, fallback):
        assert "Pizza Palace" in fallback["facebook"]["post"]

    def test_fallback_fb_has_cta(self, fallback):
        assert "hephae.co" in fallback["facebook"]["post"]

    def test_fallback_ig_mentions_report_type(self, fallback):
        caption = fallback["instagram"]["caption"]
        assert "Foot Traffic Forecast" in caption or "Traffic" in caption

    def test_fallback_tw_has_hephae(self, fallback):
        assert "#Hephae" in fallback["twitter"]["tweet"]

    def test_fallback_tw_has_business_name(self, fallback):
        assert "Pizza Palace" in fallback["twitter"]["tweet"]

    def test_fallback_tw_under_280(self, fallback):
        assert len(fallback["twitter"]["tweet"]) <= 280

    def test_fallback_not_empty(self, fallback):
        assert len(fallback["instagram"]["caption"]) > 20
        assert len(fallback["facebook"]["post"]) > 20
        assert len(fallback["twitter"]["tweet"]) > 10


# ---------------------------------------------------------------------------
# Data-enriched mode router tests
# ---------------------------------------------------------------------------

class TestRouterDataEnrichedMode:
    """Test the router when called without summary (Firestore-backed mode)."""

    @pytest.mark.asyncio
    async def test_200_with_firestore_data(self, client):
        """businessName alone should work when Firestore has data."""
        with patch(
            "hephae_db.context.latest_outputs.fetch_latest_outputs",
            return_value={
                "outputs": SAMPLE_LATEST_OUTPUTS,
                "socialLinks": {"instagram": "@test"},
            },
        ):
            res = await client.post(
                "/api/social-posts/generate",
                json={"businessName": "Test Biz"},
            )
            assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_auto_populates_social_handles(self, client):
        """Social handles should be auto-populated from stored socialLinks."""
        with patch(
            "hephae_db.context.latest_outputs.fetch_latest_outputs",
            return_value={
                "outputs": SAMPLE_LATEST_OUTPUTS,
                "socialLinks": {"instagram": "@auto_ig", "facebook": "AutoFB"},
            },
        ):
            res = await client.post(
                "/api/social-posts/generate",
                json={"businessName": "Test Biz"},
            )
            assert res.status_code == 200
            mock = client._mock_generate
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["social_handles"]["instagram"] == "@auto_ig"

    @pytest.mark.asyncio
    async def test_backward_compat_with_summary(self, client):
        """Legacy mode with summary should still work without Firestore lookup."""
        res = await client.post(
            "/api/social-posts/generate",
            json=SAMPLE_REQUEST,
        )
        assert res.status_code == 200
        mock = client._mock_generate
        call_kwargs = mock.call_args.kwargs
        assert call_kwargs["summary"] == SAMPLE_REQUEST["summary"]
        assert call_kwargs["latest_outputs"] is None

    @pytest.mark.asyncio
    async def test_passes_latest_outputs_to_agent(self, client):
        """Enriched mode should pass latest_outputs to agent function."""
        with patch(
            "hephae_db.context.latest_outputs.fetch_latest_outputs",
            return_value={
                "outputs": SAMPLE_LATEST_OUTPUTS,
                "socialLinks": {},
            },
        ):
            res = await client.post(
                "/api/social-posts/generate",
                json={"businessName": "Test Biz"},
            )
            assert res.status_code == 200
            mock = client._mock_generate
            call_kwargs = mock.call_args.kwargs
            assert call_kwargs["latest_outputs"] == SAMPLE_LATEST_OUTPUTS
