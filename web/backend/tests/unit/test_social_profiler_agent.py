"""Unit tests for SocialProfilerAgent wiring and pipeline structure."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.config import AgentModels
from backend.agents.shared_tools import crawl4ai_advanced_tool, crawl4ai_deep_tool, google_search_tool
from backend.agents.discovery.agent import (
    discovery_pipeline,
    discovery_fan_out,
    site_crawler_agent,
    social_profiler_agent,
    menu_agent,
    competitor_agent,
    _with_social_urls,
)


class TestSocialProfilerAgentConfig:
    def test_agent_has_google_search_tool(self):
        assert google_search_tool in social_profiler_agent.tools, \
            "SocialProfilerAgent must have google_search_tool as primary tool"

    def test_agent_has_crawl4ai_advanced_tool(self):
        assert crawl4ai_advanced_tool in social_profiler_agent.tools, \
            "SocialProfilerAgent must have crawl4ai_advanced_tool as supplementary tool"

    def test_agent_has_two_tools(self):
        assert len(social_profiler_agent.tools) == 2, \
            f"SocialProfilerAgent should have 2 tools, got {len(social_profiler_agent.tools)}"

    def test_agent_output_key(self):
        assert social_profiler_agent.output_key == "socialProfileMetrics"

    def test_agent_uses_fast_model(self):
        assert social_profiler_agent.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_name(self):
        assert social_profiler_agent.name == "SocialProfilerAgent"


class TestPipelineStructure:
    def test_pipeline_is_four_stage(self):
        subs = discovery_pipeline.sub_agents
        assert len(subs) == 4, f"Expected 4 stages, got {len(subs)}"
        assert subs[0].name == "SiteCrawlerAgent"
        assert subs[1].name == "DiscoveryFanOut"
        assert subs[2].name == "SocialProfilerAgent"
        assert subs[3].name == "DiscoveryReviewerAgent"

    def test_fan_out_has_eight_agents(self):
        assert len(discovery_fan_out.sub_agents) == 8


class TestWithSocialUrlsHelper:
    def test_injects_social_data_from_state(self):
        base = "You are a Social Profile Analyst."
        builder = _with_social_urls(base)

        ctx = SimpleNamespace(state={
            "socialData": json.dumps({"instagram": "https://instagram.com/test", "facebook": None}),
        })
        result = builder(ctx)

        assert "You are a Social Profile Analyst." in result
        assert "--- SOCIAL PROFILE URLS ---" in result
        assert "instagram.com/test" in result

    def test_handles_dict_state(self):
        base = "Analyze profiles."
        builder = _with_social_urls(base)

        ctx = SimpleNamespace(state={
            "socialData": {"yelp": "https://yelp.com/biz/test"},
        })
        result = builder(ctx)

        assert "yelp.com/biz/test" in result

    def test_handles_empty_state(self):
        base = "Analyze profiles."
        builder = _with_social_urls(base)

        ctx = SimpleNamespace(state={})
        result = builder(ctx)

        assert "Analyze profiles." in result
        assert "--- SOCIAL PROFILE URLS ---" in result

    def test_handles_missing_state_attr(self):
        base = "Analyze profiles."
        builder = _with_social_urls(base)

        ctx = SimpleNamespace()  # no .state attribute
        result = builder(ctx)

        assert "Analyze profiles." in result


class TestExistingAgentToolUpgrades:
    def test_site_crawler_has_advanced_and_deep_tools(self):
        tools = site_crawler_agent.tools
        assert len(tools) == 4, f"SiteCrawlerAgent should have 4 tools, got {len(tools)}"

    def test_menu_agent_has_advanced_and_deep_tools(self):
        tools = menu_agent.tools
        assert len(tools) == 3, f"MenuAgent should have 3 tools, got {len(tools)}"

    def test_competitor_agent_has_advanced_tool(self):
        tools = competitor_agent.tools
        assert len(tools) == 3, f"CompetitorAgent should have 3 tools, got {len(tools)}"
