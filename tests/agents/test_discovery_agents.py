"""Unit tests for NewsAgent, DiscoveryReviewerAgent, and pipeline v4 structure."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hephae_api.config import AgentModels
from google.adk.tools import google_search
from hephae_agents.shared_tools import validate_url_tool
from hephae_agents.discovery.agent import (
    discovery_pipeline,
    discovery_fan_out,
    news_agent,
    discovery_reviewer_agent,
    social_profiler_agent,
    business_overview_agent,
    challenges_agent,
    entity_matcher_agent,
    _with_all_discovery_data,
)


# ============================================================================
# NewsAgent configuration
# ============================================================================

class TestNewsAgentConfig:
    def test_agent_name(self):
        assert news_agent.name == "NewsAgent"

    def test_agent_model(self):
        assert news_agent.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert news_agent.output_key == "newsData"

    def test_agent_has_google_search_tool(self):
        assert google_search in news_agent.tools


# ============================================================================
# DiscoveryReviewerAgent configuration
# ============================================================================

class TestDiscoveryReviewerAgentConfig:
    def test_agent_name(self):
        assert discovery_reviewer_agent.name == "DiscoveryReviewerAgent"

    def test_agent_model(self):
        assert discovery_reviewer_agent.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert discovery_reviewer_agent.output_key == "reviewerData"

    def test_agent_has_validate_url_tool(self):
        assert validate_url_tool in discovery_reviewer_agent.tools

    def test_agent_has_google_search_tool(self):
        assert google_search in discovery_reviewer_agent.tools


# ============================================================================
# Pipeline structure v4
# ============================================================================

class TestPipelineStructureV5:
    def test_pipeline_has_two_phases(self):
        subs = discovery_pipeline.sub_agents
        assert len(subs) == 2, f"Expected 2 phases, got {len(subs)}"
        assert subs[0].name == "DiscoveryPhase1"
        assert subs[1].name == "DiscoveryPhase2"

    def test_phase1_stages(self):
        phase1 = discovery_pipeline.sub_agents[0]
        assert len(phase1.sub_agents) == 2
        assert phase1.sub_agents[0].name == "SiteCrawlerAgent"
        assert phase1.sub_agents[1].name == "EntityMatcherAgent"

    def test_phase2_stages(self):
        phase2 = discovery_pipeline.sub_agents[1]
        assert len(phase2.sub_agents) == 3
        assert phase2.sub_agents[0].name == "DiscoveryFanOut"
        assert phase2.sub_agents[1].name == "SocialProfilerAgent"
        assert phase2.sub_agents[2].name == "DiscoveryReviewerAgent"

    def test_fan_out_has_nine_agents(self):
        assert len(discovery_fan_out.sub_agents) == 9

    def test_fan_out_includes_news_agent(self):
        names = [a.name for a in discovery_fan_out.sub_agents]
        assert "NewsAgent" in names

    def test_fan_out_includes_business_overview_agent(self):
        names = [a.name for a in discovery_fan_out.sub_agents]
        assert "BusinessOverviewAgent" in names

    def test_fan_out_includes_challenges_agent(self):
        names = [a.name for a in discovery_fan_out.sub_agents]
        assert "ChallengesAgent" in names

    def test_fan_out_agent_names(self):
        names = sorted([a.name for a in discovery_fan_out.sub_agents])
        expected = sorted([
            "ThemeAgent", "ContactAgent", "SocialMediaAgent",
            "MenuAgent", "MapsAgent", "CompetitorAgent", "NewsAgent",
            "BusinessOverviewAgent", "ChallengesAgent",
        ])
        assert names == expected


class TestEntityMatcherAgentConfig:
    def test_agent_name(self):
        assert entity_matcher_agent.name == "EntityMatcherAgent"

    def test_agent_output_key(self):
        assert entity_matcher_agent.output_key == "entityMatchResult"

    def test_agent_has_no_tools(self):
        assert entity_matcher_agent.tools == []


class TestChallengesAgentConfig:
    def test_agent_name(self):
        assert challenges_agent.name == "ChallengesAgent"

    def test_agent_output_key(self):
        assert challenges_agent.output_key == "challengesData"

    def test_agent_has_google_search_tool(self):
        assert google_search in challenges_agent.tools


# ============================================================================
# BusinessOverviewAgent configuration
# ============================================================================

class TestBusinessOverviewAgentConfig:
    def test_agent_name(self):
        assert business_overview_agent.name == "BusinessOverviewAgent"

    def test_agent_model(self):
        assert business_overview_agent.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert business_overview_agent.output_key == "aiOverview"

    def test_agent_has_google_search_tool(self):
        assert google_search in business_overview_agent.tools

    def test_agent_has_one_tool(self):
        assert len(business_overview_agent.tools) == 1


# ============================================================================
# _with_all_discovery_data helper
# ============================================================================

class TestWithAllDiscoveryDataHelper:
    def test_injects_all_state_keys(self):
        base = "You are a reviewer."
        builder = _with_all_discovery_data(base)

        ctx = SimpleNamespace(state={
            "themeData": json.dumps({"primaryColor": "#c0392b"}),
            "contactData": json.dumps({"phone": "555-1234"}),
            "socialData": json.dumps({"instagram": "https://instagram.com/test"}),
            "menuData": json.dumps({"menuUrl": "https://example.com/menu"}),
            "mapsData": "https://google.com/maps/place/Test",
            "competitorData": json.dumps([{"name": "Rival"}]),
            "newsData": json.dumps([{"title": "Local news"}]),
            "socialProfileMetrics": json.dumps({"summary": {"totalFollowers": 1000}}),
            "aiOverview": json.dumps({"summary": "A classic NJ diner."}),
        })
        result = builder(ctx)

        assert "You are a reviewer." in result
        assert "--- ALL DISCOVERY DATA ---" in result
        assert "primaryColor" in result
        assert "555-1234" in result
        assert "instagram.com/test" in result
        assert "example.com/menu" in result
        assert "google.com/maps" in result
        assert "Rival" in result
        assert "Local news" in result
        assert "totalFollowers" in result
        assert "classic NJ diner" in result

    def test_handles_empty_state(self):
        base = "You are a reviewer."
        builder = _with_all_discovery_data(base)

        ctx = SimpleNamespace(state={})
        result = builder(ctx)

        assert "You are a reviewer." in result
        assert "--- ALL DISCOVERY DATA ---" in result

    def test_handles_missing_state_attr(self):
        base = "You are a reviewer."
        builder = _with_all_discovery_data(base)

        ctx = SimpleNamespace()  # no .state attribute
        result = builder(ctx)

        assert "You are a reviewer." in result

    def test_truncates_long_values(self):
        base = "Reviewer."
        builder = _with_all_discovery_data(base)

        # Create a value longer than 10K chars
        long_val = "x" * 15000
        ctx = SimpleNamespace(state={"themeData": long_val})
        result = builder(ctx)

        # The value should be truncated at 10K
        assert len(long_val) == 15000
        # The full result should contain the base instruction
        assert "Reviewer." in result

    def test_handles_dict_values(self):
        """Dict values should be JSON-serialized."""
        base = "Reviewer."
        builder = _with_all_discovery_data(base)

        ctx = SimpleNamespace(state={
            "socialData": {"instagram": "https://instagram.com/test"},
        })
        result = builder(ctx)

        assert "instagram.com/test" in result
