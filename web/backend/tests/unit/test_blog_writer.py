"""
Unit tests for blog writer agent + POST /api/blog/generate.

Covers:
- Agent-level: generate_blog_post() with mocked ADK runners
- Data context builder: _build_data_context()
- Router-level: input validation, response shape, hero stats picker
- Template: build_blog_report() produces valid HTML
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Test data
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

SAMPLE_BLOG_RESULT = {
    "title": "Bosphorus Kitchen Is Bleeding Money",
    "html_content": (
        "<h1>Bosphorus Kitchen Is Bleeding Money</h1>"
        "<p>Every month, $847 walks out the door.</p>"
        "<h2>The Data</h2>"
        "<p>Twelve menu items analyzed. Score: 62/100.</p>"
        "<blockquote>Profit leakage is real.</blockquote>"
        "<h2>What This Means</h2>"
        "<p>Time to reprice.</p>"
        "<p>Get your own analysis at <a href=\"https://hephae.co\">hephae.co</a>.</p>"
    ),
    "research_brief": {
        "narrative_hook": "Every month, $847 walks out the door.",
        "key_findings": [
            {"stat": "$847/mo", "context": "profit leakage", "source_report": "margin"},
        ],
        "cross_insights": ["Low SEO + high leakage = double trouble"],
        "recommended_angle": "The hidden cost of bad pricing",
    },
    "word_count": 42,
    "data_sources": ["margin_surgeon", "seo_auditor"],
}

SAMPLE_HERO_BYTES = b"\x89PNG\r\n\x1a\nfake-hero-image-bytes"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_stream(*a, **kw):
    async def _gen():
        return
        yield
    return _gen()


# ---------------------------------------------------------------------------
# Agent: _build_data_context tests
# ---------------------------------------------------------------------------

class TestBuildDataContext:
    """Test _build_data_context helper."""

    def test_includes_business_name(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("My Cafe", SAMPLE_LATEST_OUTPUTS)
        assert "My Cafe" in ctx

    def test_includes_margin_data(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "$847" in ctx
        assert "62/100" in ctx
        assert "12" in ctx
        assert "Margin Surgery" in ctx

    def test_includes_seo_data(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "75/100" in ctx
        assert "Technical: 85" in ctx
        assert "Content: 55" in ctx
        assert "SEO Audit" in ctx

    def test_includes_report_urls(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "https://example.com/margin.html" in ctx
        assert "https://example.com/seo.html" in ctx

    def test_includes_available_reports_list(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("Biz", SAMPLE_LATEST_OUTPUTS)
        assert "Available Reports:" in ctx
        assert "Margin Surgery" in ctx
        assert "SEO Deep Audit" in ctx

    def test_handles_traffic_data(self):
        from backend.agents.blog_writer.agent import _build_data_context
        outputs = {"traffic_forecaster": {"peak_slot_score": 92, "summary": "Saturday peak"}}
        ctx = _build_data_context("Biz", outputs)
        assert "92" in ctx
        assert "Traffic Forecast" in ctx

    def test_handles_competitive_data(self):
        from backend.agents.blog_writer.agent import _build_data_context
        outputs = {"competitive_analyzer": {"competitor_count": 5, "avg_threat_level": 7.2, "summary": "High competition"}}
        ctx = _build_data_context("Biz", outputs)
        assert "5" in ctx
        assert "7.2/10" in ctx

    def test_handles_marketing_data(self):
        from backend.agents.blog_writer.agent import _build_data_context
        outputs = {"marketing_swarm": {"summary": "Focus on Instagram Reels"}}
        ctx = _build_data_context("Biz", outputs)
        assert "Focus on Instagram Reels" in ctx
        assert "Marketing Insights" in ctx

    def test_handles_empty_outputs(self):
        from backend.agents.blog_writer.agent import _build_data_context
        ctx = _build_data_context("Biz", {})
        assert "Biz" in ctx
        assert "Available Reports:" in ctx

    def test_skips_non_dict_values(self):
        from backend.agents.blog_writer.agent import _build_data_context
        outputs = {"margin_surgeon": "not a dict", "seo_auditor": SAMPLE_LATEST_OUTPUTS["seo_auditor"]}
        ctx = _build_data_context("Biz", outputs)
        assert "Margin Surgery Data" not in ctx
        assert "SEO Audit Data" in ctx

    def test_handles_leakage_type_error(self):
        from backend.agents.blog_writer.agent import _build_data_context
        outputs = {"margin_surgeon": {"totalLeakage": "not-a-number", "score": 50}}
        ctx = _build_data_context("Biz", outputs)
        assert "not-a-number" in ctx


# ---------------------------------------------------------------------------
# Agent: _parse_json tests
# ---------------------------------------------------------------------------

class TestBlogParseJson:
    """Test _parse_json helper in blog writer."""

    def test_plain_json(self):
        from backend.agents.blog_writer.agent import _parse_json
        assert _parse_json('{"key": "val"}') == {"key": "val"}

    def test_fenced_json(self):
        from backend.agents.blog_writer.agent import _parse_json
        assert _parse_json('```json\n{"key": "val"}\n```') == {"key": "val"}

    def test_dict_passthrough(self):
        from backend.agents.blog_writer.agent import _parse_json
        assert _parse_json({"key": "val"}) == {"key": "val"}

    def test_invalid_returns_empty(self):
        from backend.agents.blog_writer.agent import _parse_json
        assert _parse_json("broken") == {}


# ---------------------------------------------------------------------------
# Agent: generate_blog_post tests
# ---------------------------------------------------------------------------

class TestGenerateBlogPost:
    """Test generate_blog_post() with mocked ADK runners."""

    @pytest.mark.asyncio
    async def test_returns_expected_keys(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            # Mock research compiler session → JSON brief
            rc_session = MagicMock()
            rc_session.state = {
                "researchBrief": json.dumps({
                    "narrative_hook": "Every month, $847 walks out.",
                    "key_findings": [{"stat": "$847/mo", "context": "leakage", "source_report": "margin"}],
                    "cross_insights": [],
                    "recommended_angle": "Hidden costs",
                })
            }
            # Mock blog writer session → HTML content
            bw_session = MagicMock()
            bw_session.state = {
                "blogContent": (
                    "<h1>Test Blog Title</h1>"
                    "<p>Some content about profits and data.</p>"
                )
            }

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                if idx == 0:
                    return rc_session
                return bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Test Biz", SAMPLE_LATEST_OUTPUTS)

            assert "title" in result
            assert "html_content" in result
            assert "research_brief" in result
            assert "word_count" in result
            assert "data_sources" in result

    @pytest.mark.asyncio
    async def test_extracts_title_from_h1(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            rc_session = MagicMock()
            rc_session.state = {"researchBrief": "{}"}
            bw_session = MagicMock()
            bw_session.state = {"blogContent": "<h1>My Custom Blog Title</h1><p>Body text.</p>"}

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                return rc_session if idx == 0 else bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Biz", {"margin_surgeon": {"score": 50}})

            assert result["title"] == "My Custom Blog Title"

    @pytest.mark.asyncio
    async def test_fallback_title_when_no_h1(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            rc_session = MagicMock()
            rc_session.state = {"researchBrief": "{}"}
            bw_session = MagicMock()
            bw_session.state = {"blogContent": "<p>No heading here.</p>"}

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                return rc_session if idx == 0 else bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Cool Cafe", {"margin_surgeon": {"score": 50}})

            assert result["title"] == "Hephae Analysis: Cool Cafe"

    @pytest.mark.asyncio
    async def test_counts_words_correctly(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            rc_session = MagicMock()
            rc_session.state = {"researchBrief": "{}"}
            bw_session = MagicMock()
            bw_session.state = {"blogContent": "<h1>Title</h1><p>One two three four five.</p>"}

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                return rc_session if idx == 0 else bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Biz", {"margin_surgeon": {"score": 50}})

            # "Title" + "One two three four five." = 6 words
            assert result["word_count"] == 6

    @pytest.mark.asyncio
    async def test_tracks_data_sources(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            rc_session = MagicMock()
            rc_session.state = {"researchBrief": "{}"}
            bw_session = MagicMock()
            bw_session.state = {"blogContent": "<h1>T</h1>"}

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                return rc_session if idx == 0 else bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Biz", SAMPLE_LATEST_OUTPUTS)

            assert "margin_surgeon" in result["data_sources"]
            assert "seo_auditor" in result["data_sources"]

    @pytest.mark.asyncio
    async def test_strips_html_fences_from_blog(self):
        with (
            patch("backend.agents.blog_writer.agent.InMemorySessionService") as mock_svc_cls,
            patch("backend.agents.blog_writer.agent.Runner") as mock_runner_cls,
        ):
            rc_session = MagicMock()
            rc_session.state = {"researchBrief": "{}"}
            bw_session = MagicMock()
            bw_session.state = {"blogContent": "```html\n<h1>Title</h1>\n```"}

            call_count = {"n": 0}
            def _make_session_get(*a, **kw):
                idx = call_count["n"]
                call_count["n"] += 1
                return rc_session if idx == 0 else bw_session

            svc = MagicMock()
            svc.create_session = AsyncMock(return_value=None)
            svc.get_session = AsyncMock(side_effect=_make_session_get)
            mock_svc_cls.return_value = svc

            runner = MagicMock()
            runner.run_async = MagicMock(side_effect=_empty_stream)
            mock_runner_cls.return_value = runner

            from backend.agents.blog_writer.agent import generate_blog_post
            result = await generate_blog_post("Biz", {"margin_surgeon": {"score": 50}})

            assert "```" not in result["html_content"]
            assert "<h1>Title</h1>" in result["html_content"]


# ---------------------------------------------------------------------------
# Agent config tests
# ---------------------------------------------------------------------------

class TestAgentConfig:
    """Test agent configuration matches expected models."""

    def test_research_compiler_uses_primary_model(self):
        from backend.agents.blog_writer.agent import research_compiler_agent
        from backend.config import AgentModels
        assert research_compiler_agent.model == AgentModels.PRIMARY_MODEL

    def test_blog_writer_uses_enhanced_model(self):
        from backend.agents.blog_writer.agent import blog_writer_agent
        from backend.config import AgentModels
        assert blog_writer_agent.model == AgentModels.ENHANCED_MODEL

    def test_research_compiler_output_key(self):
        from backend.agents.blog_writer.agent import research_compiler_agent
        assert research_compiler_agent.output_key == "researchBrief"

    def test_blog_writer_output_key(self):
        from backend.agents.blog_writer.agent import blog_writer_agent
        assert blog_writer_agent.output_key == "blogContent"

    def test_report_type_labels(self):
        from backend.agents.blog_writer.agent import REPORT_TYPE_LABELS
        assert "margin_surgeon" in REPORT_TYPE_LABELS
        assert "seo_auditor" in REPORT_TYPE_LABELS
        assert "traffic_forecaster" in REPORT_TYPE_LABELS
        assert "competitive_analyzer" in REPORT_TYPE_LABELS
        assert "marketing_swarm" in REPORT_TYPE_LABELS


# ---------------------------------------------------------------------------
# Router: _pick_hero_stats tests
# ---------------------------------------------------------------------------

class TestPickHeroStats:
    """Test _pick_hero_stats helper."""

    def test_prefers_margin_leakage(self):
        from backend.routers.blog import _pick_hero_stats
        headline, subtitle = _pick_hero_stats(SAMPLE_LATEST_OUTPUTS, "Biz")
        assert "$847" in headline
        assert "Profit Leakage" in subtitle

    def test_margin_score_fallback(self):
        from backend.routers.blog import _pick_hero_stats
        outputs = {"margin_surgeon": {"score": 72}}
        headline, subtitle = _pick_hero_stats(outputs, "Biz")
        assert "72/100" in headline
        assert "Margin Surgery Score" in subtitle

    def test_seo_fallback(self):
        from backend.routers.blog import _pick_hero_stats
        outputs = {"seo_auditor": {"score": 85}}
        headline, subtitle = _pick_hero_stats(outputs, "Biz")
        assert "85/100" in headline
        assert "SEO Audit Score" in subtitle

    def test_competitive_fallback(self):
        from backend.routers.blog import _pick_hero_stats
        outputs = {"competitive_analyzer": {"competitor_count": 8}}
        headline, subtitle = _pick_hero_stats(outputs, "Biz")
        assert "8" in headline
        assert "Competitors Analyzed" in subtitle

    def test_default_when_no_data(self):
        from backend.routers.blog import _pick_hero_stats
        headline, subtitle = _pick_hero_stats({}, "Cool Biz")
        assert headline == "Deep Dive"
        assert "Cool Biz" in subtitle

    def test_skips_non_dict_margin(self):
        from backend.routers.blog import _pick_hero_stats
        outputs = {"margin_surgeon": "not a dict", "seo_auditor": {"score": 90}}
        headline, subtitle = _pick_hero_stats(outputs, "Biz")
        assert "90/100" in headline

    def test_handles_invalid_leakage_type(self):
        from backend.routers.blog import _pick_hero_stats
        outputs = {"margin_surgeon": {"totalLeakage": "bad-value"}}
        headline, subtitle = _pick_hero_stats(outputs, "Biz")
        # Should fall through to default since float() will fail
        assert headline == "Deep Dive" or "Margin Surgery" in subtitle


# ---------------------------------------------------------------------------
# Router-level tests (POST /api/blog/generate)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def blog_client():
    with (
        patch(
            "backend.routers.blog.generate_blog_post",
            new_callable=AsyncMock,
            return_value=SAMPLE_BLOG_RESULT,
        ) as mock_blog,
        patch(
            "backend.routers.blog.generate_universal_social_card",
            new_callable=AsyncMock,
            return_value=SAMPLE_HERO_BYTES,
        ) as mock_card,
        patch(
            "backend.routers.blog.upload_report",
            new_callable=AsyncMock,
            return_value="https://storage.googleapis.com/everything-hephae/test/blog-1234.html",
        ) as mock_upload,
        patch("backend.routers.blog.build_blog_report", return_value="<html>blog</html>") as mock_template,
        patch("backend.routers.blog.write_agent_result", new_callable=AsyncMock) as mock_write,
    ):
        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._mock_blog = mock_blog  # type: ignore[attr-defined]
            ac._mock_card = mock_card  # type: ignore[attr-defined]
            ac._mock_upload = mock_upload  # type: ignore[attr-defined]
            ac._mock_template = mock_template  # type: ignore[attr-defined]
            ac._mock_write = mock_write  # type: ignore[attr-defined]
            yield ac


class TestBlogRouterValidation:
    """Test POST /api/blog/generate input validation."""

    @pytest.mark.asyncio
    async def test_400_missing_business_name(self, blog_client):
        res = await blog_client.post("/api/blog/generate", json={})
        assert res.status_code == 400
        assert "businessName" in res.json()["error"]

    @pytest.mark.asyncio
    async def test_400_empty_business_name(self, blog_client):
        res = await blog_client.post("/api/blog/generate", json={"businessName": ""})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_404_no_analysis_data(self, blog_client):
        with patch(
            "backend.routers.blog.fetch_latest_outputs",
            return_value={"outputs": {}, "socialLinks": {}},
        ):
            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Unknown Cafe"}
            )
            assert res.status_code == 404
            assert "No analysis data" in res.json()["error"]


class TestBlogRouterHappyPath:
    """Test successful blog generation via router."""

    @pytest.mark.asyncio
    async def test_200_full_response(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={"primaryColor": "#FF0000"}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Bosphorus Kitchen"}
            )
            assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_response_shape(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Test Biz"}
            )
            data = res.json()
            assert "title" in data
            assert "htmlContent" in data
            assert "reportUrl" in data
            assert "heroImageUrl" in data
            assert "wordCount" in data
            assert "dataSources" in data

    @pytest.mark.asyncio
    async def test_returns_correct_title(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Biz"}
            )
            assert res.json()["title"] == SAMPLE_BLOG_RESULT["title"]

    @pytest.mark.asyncio
    async def test_returns_report_url(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Biz"}
            )
            assert res.json()["reportUrl"] == "https://storage.googleapis.com/everything-hephae/test/blog-1234.html"

    @pytest.mark.asyncio
    async def test_calls_generate_blog_post_with_outputs(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            await blog_client.post(
                "/api/blog/generate", json={"businessName": "Biz"}
            )
            blog_client._mock_blog.assert_called_once_with("Biz", SAMPLE_LATEST_OUTPUTS)

    @pytest.mark.asyncio
    async def test_calls_social_card_for_hero(self, blog_client):
        with (
            patch(
                "backend.routers.blog.fetch_latest_outputs",
                return_value={"outputs": SAMPLE_LATEST_OUTPUTS, "socialLinks": {}},
            ),
            patch("backend.lib.db.read_business.read_business", return_value={}),
            patch("backend.lib.firebase.gcs_bucket") as mock_bucket,
        ):
            mock_blob = MagicMock()
            mock_bucket.blob.return_value = mock_blob

            await blog_client.post(
                "/api/blog/generate", json={"businessName": "Biz"}
            )
            blog_client._mock_card.assert_called_once()
            call_kwargs = blog_client._mock_card.call_args.kwargs
            assert call_kwargs["business_name"] == "Biz"
            assert call_kwargs["highlight"] == "Hephae Blog"


class TestBlogRouterErrorHandling:
    """Test error handling in the blog router."""

    @pytest.mark.asyncio
    async def test_500_on_agent_exception(self, blog_client):
        with patch(
            "backend.routers.blog.fetch_latest_outputs",
            side_effect=Exception("Firestore down"),
        ):
            res = await blog_client.post(
                "/api/blog/generate", json={"businessName": "Biz"}
            )
            assert res.status_code == 500
            assert "error" in res.json()


# ---------------------------------------------------------------------------
# Template: build_blog_report tests
# ---------------------------------------------------------------------------

class TestBuildBlogReport:
    """Test build_blog_report() produces valid HTML."""

    def test_returns_html_string(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<h1>Test</h1><p>Content</p>",
            business_name="Test Biz",
        )
        assert isinstance(html, str)
        assert "<html" in html.lower() or "<!doctype" in html.lower()

    def test_includes_article_content(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<h1>My Blog</h1><p>Specific test content here.</p>",
            business_name="Biz",
        )
        assert "Specific test content here." in html

    def test_includes_hero_image(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<p>Body</p>",
            business_name="Biz",
            hero_image_url="https://example.com/hero.png",
        )
        assert "https://example.com/hero.png" in html

    def test_no_hero_when_empty_url(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<p>Body</p>",
            business_name="Biz",
            hero_image_url="",
        )
        assert "hero" not in html.lower() or "<img" not in html.split("<article")[0]

    def test_uses_title_in_page(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<p>Body</p>",
            business_name="Biz",
            title="My Great Blog Post",
        )
        assert "My Great Blog Post" in html

    def test_fallback_title_from_business_name(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<p>Body</p>",
            business_name="Cool Cafe",
        )
        assert "Cool Cafe" in html

    def test_article_wrapped_in_article_tag(self):
        from backend.lib.report_templates import build_blog_report
        html = build_blog_report(
            article_html="<p>Test content</p>",
            business_name="Biz",
        )
        assert "<article" in html
        assert "</article>" in html


# ---------------------------------------------------------------------------
# Prompt constants tests
# ---------------------------------------------------------------------------

class TestPromptConstants:
    """Verify prompt constants exist and contain expected content."""

    def test_research_compiler_instruction_exists(self):
        from backend.agents.blog_writer.prompts import RESEARCH_COMPILER_INSTRUCTION
        assert len(RESEARCH_COMPILER_INSTRUCTION) > 100

    def test_research_compiler_mentions_json(self):
        from backend.agents.blog_writer.prompts import RESEARCH_COMPILER_INSTRUCTION
        assert "JSON" in RESEARCH_COMPILER_INSTRUCTION

    def test_blog_writer_instruction_exists(self):
        from backend.agents.blog_writer.prompts import BLOG_WRITER_INSTRUCTION
        assert len(BLOG_WRITER_INSTRUCTION) > 100

    def test_blog_writer_mentions_word_count(self):
        from backend.agents.blog_writer.prompts import BLOG_WRITER_INSTRUCTION
        assert "800" in BLOG_WRITER_INSTRUCTION
        assert "1200" in BLOG_WRITER_INSTRUCTION

    def test_blog_writer_mentions_hephae(self):
        from backend.agents.blog_writer.prompts import BLOG_WRITER_INSTRUCTION
        assert "Hephae" in BLOG_WRITER_INSTRUCTION

    def test_blog_writer_mentions_html(self):
        from backend.agents.blog_writer.prompts import BLOG_WRITER_INSTRUCTION
        assert "<h1>" in BLOG_WRITER_INSTRUCTION


# ---------------------------------------------------------------------------
# Types tests
# ---------------------------------------------------------------------------

class TestBlogPostResponse:
    """Test BlogPostResponse Pydantic model."""

    def test_default_values(self):
        from backend.types import BlogPostResponse
        resp = BlogPostResponse()
        assert resp.title == ""
        assert resp.word_count == 0
        assert resp.data_sources == []

    def test_from_dict(self):
        from backend.types import BlogPostResponse
        resp = BlogPostResponse(
            title="Test",
            htmlContent="<p>Hi</p>",
            reportUrl="https://example.com",
            heroImageUrl="https://example.com/hero.png",
            wordCount=100,
            dataSources=["margin_surgeon"],
        )
        assert resp.title == "Test"
        assert resp.word_count == 100
        assert resp.data_sources == ["margin_surgeon"]

    def test_alias_serialization(self):
        from backend.types import BlogPostResponse
        resp = BlogPostResponse(title="T", wordCount=50, dataSources=["seo"])
        data = resp.model_dump(by_alias=True)
        assert "wordCount" in data
        assert "dataSources" in data
        assert "htmlContent" in data
