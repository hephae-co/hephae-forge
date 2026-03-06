"""Unit tests for Cloud Cost Optimizer agents and tools."""

from __future__ import annotations

import pytest

from backend.config import AgentModels
from backend.optimizer.cloud_cost_optimizer.agent import (
    cloud_cost_optimization_pipeline,
    cloud_analysis_fan_out,
    storage_analyzer,
    firestore_analyzer,
    bq_analyzer,
    cloud_recommender,
)
from backend.optimizer.cloud_cost_optimizer.tools import (
    analyze_gcs_usage,
    analyze_firestore_patterns,
    analyze_bq_usage,
    estimate_cloud_costs,
)


# ============================================================================
# Agent configuration
# ============================================================================

class TestStorageAnalyzerConfig:
    def test_agent_name(self):
        assert storage_analyzer.name == "StorageAnalyzer"

    def test_agent_output_key(self):
        assert storage_analyzer.output_key == "gcsAnalysis"


class TestFirestoreAnalyzerConfig:
    def test_agent_name(self):
        assert firestore_analyzer.name == "FirestoreAnalyzer"

    def test_agent_output_key(self):
        assert firestore_analyzer.output_key == "firestoreAnalysis"


class TestBQAnalyzerConfig:
    def test_agent_name(self):
        assert bq_analyzer.name == "BigQueryAnalyzer"

    def test_agent_output_key(self):
        assert bq_analyzer.output_key == "bqAnalysis"


class TestCloudRecommenderConfig:
    def test_agent_name(self):
        assert cloud_recommender.name == "CloudCostRecommender"

    def test_agent_output_key(self):
        assert cloud_recommender.output_key == "cloudCostRecommendations"


class TestPipelineStructure:
    def test_pipeline_is_two_stage(self):
        subs = cloud_cost_optimization_pipeline.sub_agents
        assert len(subs) == 2

    def test_fan_out_has_three_analyzers(self):
        assert len(cloud_analysis_fan_out.sub_agents) == 3

    def test_fan_out_agent_names(self):
        names = sorted([a.name for a in cloud_analysis_fan_out.sub_agents])
        assert names == sorted(["StorageAnalyzer", "FirestoreAnalyzer", "BigQueryAnalyzer"])

    def test_stage_order(self):
        subs = cloud_cost_optimization_pipeline.sub_agents
        assert subs[0].name == "CloudAnalysisFanOut"
        assert subs[1].name == "CloudCostRecommender"


# ============================================================================
# Tools
# ============================================================================

class TestAnalyzeGCSUsage:
    @pytest.mark.asyncio
    async def test_returns_object_types(self):
        result = await analyze_gcs_usage()
        assert len(result["object_types"]) > 0

    @pytest.mark.asyncio
    async def test_detects_no_lifecycle_policy(self):
        result = await analyze_gcs_usage()
        assert result["lifecycle_policy"] == "none_detected"

    @pytest.mark.asyncio
    async def test_has_recommendations(self):
        result = await analyze_gcs_usage()
        assert len(result["recommendations"]) > 0


class TestAnalyzeFirestorePatterns:
    @pytest.mark.asyncio
    async def test_identifies_collections(self):
        result = await analyze_firestore_patterns()
        names = [c["name"] for c in result["collections"]]
        assert "businesses" in names
        assert "cache_weather" in names

    @pytest.mark.asyncio
    async def test_identifies_manual_ttl(self):
        result = await analyze_firestore_patterns()
        assert "manual" in result["ttl_implementation"]

    @pytest.mark.asyncio
    async def test_has_recommendations(self):
        result = await analyze_firestore_patterns()
        assert len(result["recommendations"]) > 0


class TestAnalyzeBQUsage:
    @pytest.mark.asyncio
    async def test_identifies_tables(self):
        result = await analyze_bq_usage()
        assert result["total_tables"] == 3

    @pytest.mark.asyncio
    async def test_detects_no_partitioning(self):
        result = await analyze_bq_usage()
        assert result["partitioning_status"] == "none on any table"


class TestEstimateCloudCosts:
    @pytest.mark.asyncio
    async def test_returns_itemized_costs(self):
        result = await estimate_cloud_costs(
            gcs_objects_monthly=500,
            avg_size_kb=100,
            firestore_reads=50000,
            firestore_writes=5000,
            bq_storage_gb=1.0,
        )
        assert "gcs" in result
        assert "firestore" in result
        assert "bigquery" in result
        assert result["total_monthly_usd"] > 0

    @pytest.mark.asyncio
    async def test_zero_usage_zero_cost(self):
        result = await estimate_cloud_costs(0, 0, 0, 0, 0)
        assert result["total_monthly_usd"] == 0
