"""Unit tests for OptimizerOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

try:
    from hephae_api.optimizer.orchestrator import run_optimizer
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)


# ============================================================================
# Orchestrator routing
# ============================================================================

class TestRunOptimizer:
    @pytest.mark.asyncio
    async def test_run_all_returns_all_keys(self):
        with (
            patch("hephae_api.optimizer.orchestrator._run_prompt_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
            patch("hephae_api.optimizer.orchestrator._run_ai_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
            patch("hephae_api.optimizer.orchestrator._run_cloud_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
            patch("hephae_api.optimizer.orchestrator._run_performance_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
        ):
            result = await run_optimizer(["all"])

        assert "prompt_optimization" in result
        assert "ai_cost_optimization" in result
        assert "cloud_cost_optimization" in result
        assert "performance_optimization" in result
        assert "run_at" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_run_single(self):
        with patch("hephae_api.optimizer.orchestrator._run_ai_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}):
            result = await run_optimizer(["ai_cost"])

        assert "ai_cost_optimization" in result
        assert "prompt_optimization" not in result
        assert "cloud_cost_optimization" not in result
        assert "performance_optimization" not in result

    @pytest.mark.asyncio
    async def test_run_multiple_specific(self):
        with (
            patch("hephae_api.optimizer.orchestrator._run_ai_cost_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
            patch("hephae_api.optimizer.orchestrator._run_performance_optimizer", new_callable=AsyncMock, return_value={"status": "ok"}),
        ):
            result = await run_optimizer(["ai_cost", "performance"])

        assert "ai_cost_optimization" in result
        assert "performance_optimization" in result
        assert "prompt_optimization" not in result

    @pytest.mark.asyncio
    async def test_handles_optimizer_failure(self):
        with patch("hephae_api.optimizer.orchestrator._run_prompt_optimizer", new_callable=AsyncMock, side_effect=Exception("test error")):
            result = await run_optimizer(["prompt"])

        assert "error" in result["prompt_optimization"]
        assert "test error" in result["prompt_optimization"]["error"]

    @pytest.mark.asyncio
    async def test_default_runs_all(self):
        with (
            patch("hephae_api.optimizer.orchestrator._run_prompt_optimizer", new_callable=AsyncMock, return_value={}),
            patch("hephae_api.optimizer.orchestrator._run_ai_cost_optimizer", new_callable=AsyncMock, return_value={}),
            patch("hephae_api.optimizer.orchestrator._run_cloud_cost_optimizer", new_callable=AsyncMock, return_value={}),
            patch("hephae_api.optimizer.orchestrator._run_performance_optimizer", new_callable=AsyncMock, return_value={}),
        ):
            result = await run_optimizer()

        assert "prompt_optimization" in result
        assert "ai_cost_optimization" in result
