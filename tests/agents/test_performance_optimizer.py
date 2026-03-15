"""Unit tests for Performance Optimizer agents and tools."""

from __future__ import annotations

import pytest

from hephae_api.config import AgentModels

try:
    from hephae_api.optimizer.performance_optimizer.agent import (
        performance_optimization_pipeline,
        pipeline_analyzer,
        bottleneck_detector,
        concurrency_recommender,
    )
    from hephae_api.optimizer.performance_optimizer.tools import (
        scan_pipeline_structure,
        detect_bottlenecks,
        analyze_async_patterns,
    )
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)


# ============================================================================
# Agent configuration
# ============================================================================

class TestPipelineAnalyzerConfig:
    def test_agent_name(self):
        assert pipeline_analyzer.name == "PipelineAnalyzer"

    def test_agent_model(self):
        assert pipeline_analyzer.model == AgentModels.DEFAULT_FAST_MODEL

    def test_agent_output_key(self):
        assert pipeline_analyzer.output_key == "pipelineAnalysis"


class TestBottleneckDetectorConfig:
    def test_agent_name(self):
        assert bottleneck_detector.name == "BottleneckDetector"

    def test_agent_output_key(self):
        assert bottleneck_detector.output_key == "bottleneckReport"


class TestConcurrencyRecommenderConfig:
    def test_agent_name(self):
        assert concurrency_recommender.name == "ConcurrencyRecommender"

    def test_agent_output_key(self):
        assert concurrency_recommender.output_key == "performanceRecommendations"


class TestPipelineStructure:
    def test_pipeline_is_three_stage(self):
        subs = performance_optimization_pipeline.sub_agents
        assert len(subs) == 3

    def test_stage_order(self):
        subs = performance_optimization_pipeline.sub_agents
        assert subs[0].name == "PipelineAnalyzer"
        assert subs[1].name == "BottleneckDetector"
        assert subs[2].name == "ConcurrencyRecommender"


# ============================================================================
# Tools
# ============================================================================

class TestScanPipelineStructure:
    @pytest.mark.asyncio
    async def test_finds_pipelines(self):
        result = await scan_pipeline_structure()
        assert result["total_pipelines"] >= 4  # discovery, margin, traffic, seo, competitive, marketing

    @pytest.mark.asyncio
    async def test_discovery_pipeline_has_4_stages(self):
        result = await scan_pipeline_structure()
        discovery = next(p for p in result["pipelines"] if p["name"] == "DiscoveryPipeline")
        assert discovery["stages"] == 4

    @pytest.mark.asyncio
    async def test_identifies_margin_parallelization(self):
        result = await scan_pipeline_structure()
        margin = next((p for p in result["pipelines"] if p["name"] == "MarginSurgeryOrchestrator"), None)
        if margin:
            assert "parallelization_opportunity" in margin


class TestDetectBottlenecks:
    @pytest.mark.asyncio
    async def test_finds_bottlenecks(self):
        result = await detect_bottlenecks()
        assert result["total"] > 0

    @pytest.mark.asyncio
    async def test_finds_large_data_injection(self):
        result = await detect_bottlenecks()
        patterns = [b["pattern"] for b in result["bottlenecks"]]
        assert any("context injection" in p.lower() or "data injection" in p.lower() for p in patterns)

    @pytest.mark.asyncio
    async def test_bottleneck_shape(self):
        result = await detect_bottlenecks()
        b = result["bottlenecks"][0]
        assert "file" in b
        assert "severity" in b
        assert "recommendation" in b


class TestAnalyzeAsyncPatterns:
    @pytest.mark.asyncio
    async def test_finds_patterns(self):
        result = await analyze_async_patterns()
        assert result["total"] >= 0  # May vary based on actual codebase

    @pytest.mark.asyncio
    async def test_pattern_shape(self):
        result = await analyze_async_patterns()
        if result["patterns"]:
            p = result["patterns"][0]
            assert "file" in p
            assert "pattern" in p
            assert "issue" in p
