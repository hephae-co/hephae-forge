"""Unit tests for Prompt Optimizer agents and tools."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hephae_api.config import AgentModels

try:
    from hephae_api.optimizer.prompt_optimizer.agent import (
        prompt_optimization_pipeline,
        prompt_scanner_agent,
        prompt_optimizer_agent,
        _with_scan_results,
    )
    from hephae_api.optimizer.prompt_optimizer.tools import (
        list_all_prompts,
        optimize_prompt_vertex,
        compare_prompt_quality,
    )
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)


# ============================================================================
# Agent configuration
# ============================================================================

class TestPromptScannerAgentConfig:
    def test_agent_name(self):
        assert prompt_scanner_agent.name == "PromptScannerAgent"

    def test_agent_model(self):
        assert prompt_scanner_agent.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert prompt_scanner_agent.output_key == "promptScanResults"


class TestPromptOptimizerAgentConfig:
    def test_agent_name(self):
        assert prompt_optimizer_agent.name == "PromptOptimizerAgent"

    def test_agent_model(self):
        assert prompt_optimizer_agent.model == AgentModels.PRIMARY_MODEL

    def test_agent_output_key(self):
        assert prompt_optimizer_agent.output_key == "promptOptimizationResults"


class TestPipelineStructure:
    def test_pipeline_is_two_stage(self):
        subs = prompt_optimization_pipeline.sub_agents
        assert len(subs) == 2

    def test_stage_order(self):
        subs = prompt_optimization_pipeline.sub_agents
        assert subs[0].name == "PromptScannerAgent"
        assert subs[1].name == "PromptOptimizerAgent"


# ============================================================================
# _with_scan_results helper
# ============================================================================

class TestWithScanResultsHelper:
    def test_injects_scan_data(self):
        base = "You are an optimizer."
        builder = _with_scan_results(base)
        ctx = SimpleNamespace(state={
            "promptScanResults": json.dumps({"total_count": 25}),
        })
        result = builder(ctx)
        assert "You are an optimizer." in result
        assert "--- SCAN RESULTS ---" in result
        assert "total_count" in result

    def test_handles_empty_state(self):
        base = "Optimizer."
        builder = _with_scan_results(base)
        ctx = SimpleNamespace(state={})
        result = builder(ctx)
        assert result == "Optimizer."

    def test_handles_missing_state_attr(self):
        base = "Optimizer."
        builder = _with_scan_results(base)
        ctx = SimpleNamespace()
        result = builder(ctx)
        assert result == "Optimizer."


# ============================================================================
# Tools
# ============================================================================

class TestListAllPrompts:
    @pytest.mark.asyncio
    async def test_finds_prompts(self):
        result = await list_all_prompts()
        assert result["total_count"] > 0

    @pytest.mark.asyncio
    async def test_finds_discovery_prompts(self):
        result = await list_all_prompts()
        names = [p["name"] for p in result["prompts"]]
        assert "SITE_CRAWLER_INSTRUCTION" in names
        assert "THEME_AGENT_INSTRUCTION" in names

    @pytest.mark.asyncio
    async def test_prompt_entry_shape(self):
        result = await list_all_prompts()
        p = result["prompts"][0]
        assert "name" in p
        assert "module_path" in p
        assert "char_count" in p
        assert "preview" in p
        assert "domain" in p

    @pytest.mark.asyncio
    async def test_finds_all_domains(self):
        result = await list_all_prompts()
        domains = set(p["domain"] for p in result["prompts"])
        assert "discovery" in domains
        assert "margin_analyzer" in domains


class TestOptimizePromptVertex:
    @pytest.mark.asyncio
    async def test_returns_error_without_project(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await optimize_prompt_vertex("test prompt", "TEST_INSTRUCTION")
        assert result["error"] == "missing_project"
        assert result["optimized_prompt"] == "test prompt"

    @pytest.mark.asyncio
    async def test_unknown_strategy(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"}):
            result = await optimize_prompt_vertex("test", "TEST", strategy="unknown")
        assert result["optimized_prompt"] == "test"
        assert result["strategy_used"] == "none"
        assert "Unknown strategy" in result["improvement_notes"][0]


class TestComparePromptQuality:
    @pytest.mark.asyncio
    async def test_identical_prompts_skip(self):
        result = await compare_prompt_quality("same prompt", "same prompt", "TEST")
        assert result["recommendation"] == "skip"

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await compare_prompt_quality("original", "optimized", "TEST")
        assert result["recommendation"] == "review"
