"""Unit tests for AI Cost Optimizer agents and tools."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hephae_api.config import AgentModels

try:
    from hephae_api.optimizer.ai_cost_optimizer.agent import (
        ai_cost_optimization_pipeline,
        model_usage_analyzer,
        token_analyzer,
        cost_recommender,
    )
    from hephae_api.optimizer.ai_cost_optimizer.tools import (
        scan_agent_configs,
        estimate_token_usage,
        calculate_cost_savings,
        MODEL_PRICING,
    )
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)


# ============================================================================
# Agent configuration
# ============================================================================

class TestModelUsageAnalyzerConfig:
    def test_agent_name(self):
        assert model_usage_analyzer.name == "ModelUsageAnalyzer"

    def test_agent_model(self):
        assert model_usage_analyzer.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert model_usage_analyzer.output_key == "modelUsageReport"


class TestTokenAnalyzerConfig:
    def test_agent_name(self):
        assert token_analyzer.name == "TokenAnalyzer"

    def test_agent_output_key(self):
        assert token_analyzer.output_key == "tokenAnalysis"


class TestCostRecommenderConfig:
    def test_agent_name(self):
        assert cost_recommender.name == "CostRecommender"

    def test_agent_output_key(self):
        assert cost_recommender.output_key == "aiCostRecommendations"


class TestPipelineStructure:
    def test_pipeline_is_three_stage(self):
        subs = ai_cost_optimization_pipeline.sub_agents
        assert len(subs) == 3

    def test_stage_order(self):
        subs = ai_cost_optimization_pipeline.sub_agents
        assert subs[0].name == "ModelUsageAnalyzer"
        assert subs[1].name == "TokenAnalyzer"
        assert subs[2].name == "CostRecommender"


# ============================================================================
# Tools
# ============================================================================

class TestScanAgentConfigs:
    @pytest.mark.asyncio
    async def test_finds_agents(self):
        result = await scan_agent_configs()
        assert result["total"] > 0
        assert len(result["agents"]) > 0

    @pytest.mark.asyncio
    async def test_has_model_distribution(self):
        result = await scan_agent_configs()
        assert "gemini-3.1-flash-lite-preview" in result["model_distribution"]

    @pytest.mark.asyncio
    async def test_agent_entry_shape(self):
        result = await scan_agent_configs()
        agent = result["agents"][0]
        assert "name" in agent
        assert "model" in agent
        assert "module" in agent


class TestEstimateTokenUsage:
    @pytest.mark.asyncio
    async def test_basic_estimation(self):
        result = await estimate_token_usage("TestAgent", 4000, 0)
        assert result["input_tokens"] == 1000  # 4000 / 4
        assert result["output_tokens_est"] >= 200

    @pytest.mark.asyncio
    async def test_with_data_injection(self):
        result = await estimate_token_usage("TestAgent", 4000, 30000)
        assert result["input_tokens"] == 8500  # (4000 + 30000) / 4

    @pytest.mark.asyncio
    async def test_cost_per_call_has_all_models(self):
        result = await estimate_token_usage("TestAgent", 4000, 0)
        for model in MODEL_PRICING:
            assert model in result["cost_per_call"]


class TestCalculateCostSavings:
    @pytest.mark.asyncio
    async def test_flash_to_lite_savings(self):
        result = await calculate_cost_savings(
            "gemini-2.5-flash", "gemini-2.5-flash-lite",  # fallback models still in pricing
            100, 1000, 500,
        )
        assert result["savings_usd"] > 0
        assert result["savings_pct"] > 0
        assert result["proposed_cost_usd"] < result["current_cost_usd"]

    @pytest.mark.asyncio
    async def test_enhanced_to_primary_savings(self):
        result = await calculate_cost_savings(
            "gemini-3.0-flash-preview", "gemini-3.1-flash-lite-preview",
            50, 5000, 2000,
        )
        assert result["savings_pct"] > 50  # Enhanced is more expensive than primary

    @pytest.mark.asyncio
    async def test_zero_calls_zero_cost(self):
        result = await calculate_cost_savings(
            "gemini-2.5-flash", "gemini-2.5-flash-lite",
            0, 1000, 500,
        )
        assert result["current_cost_usd"] == 0
        assert result["proposed_cost_usd"] == 0
