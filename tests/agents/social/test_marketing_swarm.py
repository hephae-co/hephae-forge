"""Unit tests for the marketing swarm pipeline (SequentialAgent)."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from google.adk.agents import SequentialAgent, LlmAgent
from hephae_agents.social.marketing_swarm.agent import (
    marketing_pipeline,
    creative_director_agent,
    platform_router_agent,
    copywriter_agent,
    run_marketing_pipeline,
    _copywriter_instruction,
)


class TestMarketingPipelineStructure:
    def test_marketing_pipeline_is_sequential_agent(self):
        assert isinstance(marketing_pipeline, SequentialAgent)

    def test_marketing_pipeline_has_three_sub_agents(self):
        assert len(marketing_pipeline.sub_agents) == 3

    def test_sub_agents_are_correct_types(self):
        for agent in marketing_pipeline.sub_agents:
            assert isinstance(agent, LlmAgent)

    def test_creative_director_in_sub_agents(self):
        names = [a.name for a in marketing_pipeline.sub_agents]
        assert "CreativeDirectorAgent" in names

    def test_platform_router_in_sub_agents(self):
        names = [a.name for a in marketing_pipeline.sub_agents]
        assert "PlatformRouterAgent" in names

    def test_copywriter_in_sub_agents(self):
        names = [a.name for a in marketing_pipeline.sub_agents]
        assert "CopywriterAgent" in names

    def test_sub_agents_order(self):
        """CreativeDirector → PlatformRouter → Copywriter."""
        subs = marketing_pipeline.sub_agents
        assert subs[0].name == "CreativeDirectorAgent"
        assert subs[1].name == "PlatformRouterAgent"
        assert subs[2].name == "CopywriterAgent"


class TestCopywriterAgent:
    def test_copywriter_output_key(self):
        assert copywriter_agent.output_key == "contentDraft"

    def test_copywriter_has_dynamic_instruction(self):
        """instruction must be callable (dynamic, not a static string)."""
        assert callable(copywriter_agent.instruction)

    def test_copywriter_instruction_returns_string(self):
        ctx = SimpleNamespace(state={
            "creativeDirection": "Go bold and colorful",
            "platformDecision": '{"platform": "Instagram"}',
        })
        result = _copywriter_instruction(ctx)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_copywriter_instruction_includes_platform(self):
        ctx = SimpleNamespace(state={
            "creativeDirection": "Minimalist",
            "platformDecision": '{"platform": "Blog"}',
        })
        result = _copywriter_instruction(ctx)
        assert "Blog" in result

    def test_copywriter_instruction_handles_missing_state(self):
        """Should not raise when state keys are missing."""
        ctx = SimpleNamespace(state={})
        result = _copywriter_instruction(ctx)
        assert isinstance(result, str)

    def test_copywriter_instruction_handles_no_state_attr(self):
        ctx = SimpleNamespace()
        result = _copywriter_instruction(ctx)
        assert isinstance(result, str)

    def test_copywriter_instruction_defaults_to_instagram(self):
        """When platformDecision is missing, defaults to Instagram."""
        ctx = SimpleNamespace(state={})
        result = _copywriter_instruction(ctx)
        assert "Instagram" in result


class TestCreativeDirectorAgent:
    def test_agent_name(self):
        assert creative_director_agent.name == "CreativeDirectorAgent"

    def test_agent_output_key(self):
        assert creative_director_agent.output_key == "creativeDirection"


class TestPlatformRouterAgent:
    def test_agent_name(self):
        assert platform_router_agent.name == "PlatformRouterAgent"

    def test_agent_output_key(self):
        assert platform_router_agent.output_key == "platformDecision"


class TestRunMarketingPipelineSignature:
    def test_run_marketing_pipeline_exists(self):
        assert callable(run_marketing_pipeline)

    def test_run_marketing_pipeline_is_coroutine(self):
        assert inspect.iscoroutinefunction(run_marketing_pipeline)

    def test_run_marketing_pipeline_has_identity_param(self):
        sig = inspect.signature(run_marketing_pipeline)
        assert "identity" in sig.parameters

    def test_run_marketing_pipeline_has_business_context_param(self):
        sig = inspect.signature(run_marketing_pipeline)
        assert "business_context" in sig.parameters

    def test_run_marketing_pipeline_business_context_default_none(self):
        sig = inspect.signature(run_marketing_pipeline)
        assert sig.parameters["business_context"].default is None
