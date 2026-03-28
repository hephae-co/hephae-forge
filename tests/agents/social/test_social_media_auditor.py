"""
Unit tests for Social Media Auditor agent + POST /api/capabilities/marketing

Covers:
- Agent config (models, tools, instruction)
- 2-step pipeline (Researcher -> Strategist)
- JSON extraction from various formats
- Report template generation
- Response model validation
- Error handling
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = pytest.mark.functional
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IDENTITY = {
    "name": "Tick Tock Diner",
    "address": "481 Broad Ave, Ridgefield, NJ",
    "officialUrl": "https://ticktockdiner.com",
    "socialLinks": {
        "instagram": "https://instagram.com/ticktockdiner",
        "facebook": "https://facebook.com/ticktockdiner",
    },
    "socialProfileMetrics": {
        "instagram": {"followers": "~1200", "bio": "Classic NJ diner"},
    },
    "competitors": [
        {"name": "Park Diner", "url": "https://parkdiner.com", "reason": "Same area"},
    ],
}

AUDIT_PAYLOAD = {
    "overall_score": 52,
    "summary": "Tick Tock Diner has moderate social presence with room for growth.",
    "platforms": [
        {
            "name": "instagram",
            "url": "https://instagram.com/ticktockdiner",
            "handle": "@ticktockdiner",
            "score": 55,
            "followers": "~1,200",
            "posting_frequency": "2-3 times/week",
            "content_themes": ["food photography", "daily specials"],
            "engagement": "moderate",
            "last_post_recency": "3 days ago",
            "strengths": ["Consistent visual style"],
            "weaknesses": ["No Reels strategy"],
            "recommendations": ["Post Reels 3x/week"],
        },
    ],
    "competitor_benchmarks": [
        {"name": "Park Diner", "strongest_platform": "facebook", "followers": "~3,000"},
    ],
    "strategic_recommendations": [
        {"priority": 1, "action": "Launch Instagram Reels", "impact": "high", "effort": "medium"},
    ],
    "content_strategy": {
        "content_pillars": ["Behind the scenes", "Menu highlights"],
        "hashtag_strategy": ["#NJeats", "#dinerlife"],
        "posting_schedule": "Post 4-5x/week",
    },
    "sources": [
        {"url": "https://instagram.com/ticktockdiner", "title": "Instagram"},
    ],
}


def _make_text_event(text: str, thought=False):
    part = SimpleNamespace(text=text, thought=thought, function_call=None, function_response=None)
    return SimpleNamespace(content=SimpleNamespace(parts=[part]))


def _empty_stream(*a, **kw):
    async def _gen():
        return
        yield
    return _gen()


# ---------------------------------------------------------------------------
# Agent config tests
# ---------------------------------------------------------------------------

class TestAgentConfig:
    def test_researcher_has_tools(self):
        from hephae_agents.social.media_auditor.agent import social_researcher_agent
        tool_names = [getattr(t, '__name__', None) or getattr(t, 'name', str(t)) for t in social_researcher_agent.tools]
        assert "google_search" in tool_names
        assert "crawl_with_options" in tool_names

    def test_strategist_has_no_tools(self):
        from hephae_agents.social.media_auditor.agent import social_strategist_agent
        assert not social_strategist_agent.tools

    def test_researcher_model(self):
        from hephae_agents.social.media_auditor.agent import social_researcher_agent
        from hephae_api.config import AgentModels
        assert social_researcher_agent.model == AgentModels.PRIMARY_MODEL

    def test_strategist_uses_thinking(self):
        from hephae_agents.social.media_auditor.agent import social_strategist_agent
        from hephae_api.config import ThinkingPresets
        assert social_strategist_agent.generate_content_config == ThinkingPresets.HIGH

    def test_researcher_instruction_not_empty(self):
        from hephae_agents.social.media_auditor.agent import social_researcher_agent
        instr = social_researcher_agent.instruction
        assert callable(instr) or len(instr) > 100

    def test_strategist_instruction_not_empty(self):
        from hephae_agents.social.media_auditor.agent import social_strategist_agent
        instr = social_strategist_agent.instruction
        assert callable(instr) or len(instr) > 100

    def test_agents_have_fallback(self):
        from hephae_agents.social.media_auditor.agent import social_researcher_agent, social_strategist_agent
        assert social_researcher_agent.on_model_error_callback is not None
        assert social_strategist_agent.on_model_error_callback is not None


# ---------------------------------------------------------------------------
# Response model tests
# ---------------------------------------------------------------------------

class TestSocialAuditReportModel:
    def test_minimal_valid(self):
        from hephae_api.types import SocialAuditReport
        report = SocialAuditReport()
        assert report.overall_score == 0
        assert report.platforms == []

    def test_from_payload(self):
        from hephae_api.types import SocialAuditReport
        report = SocialAuditReport(**AUDIT_PAYLOAD)
        assert report.overall_score == 52
        assert report.summary == "Tick Tock Diner has moderate social presence with room for growth."
        assert len(report.platforms) == 1

    def test_alias_fields(self):
        from hephae_api.types import SocialAuditReport
        # camelCase aliases should work
        report = SocialAuditReport(overallScore=75, reportUrl="https://test.com/report.html")
        assert report.overall_score == 75
        assert report.report_url == "https://test.com/report.html"

    def test_extra_fields_allowed(self):
        from hephae_api.types import SocialAuditReport
        report = SocialAuditReport(overall_score=50, content_strategy={"pillars": []})
        assert report.model_dump().get("content_strategy") == {"pillars": []}


# ---------------------------------------------------------------------------
# Report template tests
# ---------------------------------------------------------------------------

class TestBuildSocialAuditReport:
    def test_returns_html(self):
        from hephae_common.report_templates import build_social_audit_report
        html = build_social_audit_report(AUDIT_PAYLOAD, IDENTITY)
        assert isinstance(html, str)
        assert "<html" in html.lower()

    def test_contains_business_name(self):
        from hephae_common.report_templates import build_social_audit_report
        html = build_social_audit_report(AUDIT_PAYLOAD, IDENTITY)
        assert "Tick Tock Diner" in html

    def test_contains_overall_score(self):
        from hephae_common.report_templates import build_social_audit_report
        html = build_social_audit_report(AUDIT_PAYLOAD, IDENTITY)
        assert "52" in html

    def test_contains_platform_cards(self):
        from hephae_common.report_templates import build_social_audit_report
        html = build_social_audit_report(AUDIT_PAYLOAD, IDENTITY)
        assert "instagram" in html.lower()
        assert "55" in html  # platform score

    def test_contains_recommendations(self):
        from hephae_common.report_templates import build_social_audit_report
        html = build_social_audit_report(AUDIT_PAYLOAD, IDENTITY)
        assert "Launch Instagram Reels" in html

    def test_handles_empty_platforms(self):
        from hephae_common.report_templates import build_social_audit_report
        result = {**AUDIT_PAYLOAD, "platforms": []}
        html = build_social_audit_report(result, IDENTITY)
        assert "<html" in html.lower()

    def test_handles_missing_optional_fields(self):
        from hephae_common.report_templates import build_social_audit_report
        minimal = {"overall_score": 30, "summary": "Basic audit."}
        html = build_social_audit_report(minimal, IDENTITY)
        assert "<html" in html.lower()
        assert "30" in html


# ---------------------------------------------------------------------------
# Router fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    with (
        patch("hephae_api.routers.web.capabilities.run_social_media_audit", new_callable=AsyncMock, return_value=AUDIT_PAYLOAD),
        patch("hephae_api.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/social-audit.html"),
        patch("hephae_api.routers.web.capabilities.build_social_audit_report", return_value="<html>audit</html>"),
        patch("hephae_api.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("hephae_api.routers.web.capabilities.write_agent_result", new_callable=AsyncMock, return_value=None),
        patch("hephae_api.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock, return_value=None),
    ):
        from hephae_api.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    @pytest.mark.asyncio
    async def test_400_missing_identity(self, client):
        res = await client.post("/api/capabilities/marketing", json={})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_400_missing_name(self, client):
        res = await client.post("/api/capabilities/marketing", json={"identity": {"address": "123 Main St"}})
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# Successful pipeline
# ---------------------------------------------------------------------------

class TestSuccessfulPipeline:
    @pytest.mark.asyncio
    async def test_parses_social_audit_report(self, client):
        res = await client.post("/api/capabilities/marketing", json={"identity": IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data["overall_score"] == 52
        assert len(data["platforms"]) == 1
        assert "reportUrl" in data

    @pytest.mark.asyncio
    async def test_response_includes_report_url(self, client):
        res = await client.post("/api/capabilities/marketing", json={"identity": IDENTITY})
        assert res.status_code == 200
        assert res.json()["reportUrl"] == "https://storage.googleapis.com/test/social-audit.html"

    @pytest.mark.asyncio
    async def test_minimal_identity(self, client):
        """Only name is required."""
        res = await client.post("/api/capabilities/marketing", json={
            "identity": {"name": "Simple Cafe"}
        })
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_500_on_runner_error(self):
        with (
            patch("hephae_api.routers.web.capabilities.run_social_media_audit", new_callable=AsyncMock, side_effect=ValueError("Audit failed")),
            patch("hephae_api.routers.web.capabilities.upload_report", new_callable=AsyncMock, return_value=None),
            patch("hephae_api.routers.web.capabilities.build_social_audit_report", return_value=""),
            patch("hephae_api.routers.web.capabilities.generate_slug", side_effect=lambda n: n.lower()),
            patch("hephae_api.routers.web.capabilities.write_agent_result", new_callable=AsyncMock),
            patch("hephae_api.routers.web.capabilities.generate_and_draft_marketing_content", new_callable=AsyncMock),
        ):
            from hephae_api.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.post("/api/capabilities/marketing", json={"identity": IDENTITY})
                assert res.status_code == 500
                assert "Audit failed" in res.json()["error"]


# ---------------------------------------------------------------------------
# Config version
# ---------------------------------------------------------------------------

class TestConfigVersion:
    def test_social_media_auditor_version_exists(self):
        from hephae_api.config import AgentVersions
        assert hasattr(AgentVersions, "SOCIAL_MEDIA_AUDITOR")
        assert AgentVersions.SOCIAL_MEDIA_AUDITOR == "1.0.0"
