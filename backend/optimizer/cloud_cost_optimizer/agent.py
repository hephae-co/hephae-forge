"""Cloud Cost Optimizer — parallel analysis of GCS/Firestore/BQ + cost recommender."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool

from backend.config import AgentModels
from backend.optimizer.cloud_cost_optimizer.prompts import (
    STORAGE_ANALYZER_INSTRUCTION,
    FIRESTORE_ANALYZER_INSTRUCTION,
    BQ_ANALYZER_INSTRUCTION,
    CLOUD_RECOMMENDER_INSTRUCTION,
)
from backend.optimizer.cloud_cost_optimizer.tools import (
    analyze_gcs_usage,
    analyze_firestore_patterns,
    analyze_bq_usage,
    estimate_cloud_costs,
)

analyze_gcs_usage_tool = FunctionTool(func=analyze_gcs_usage)
analyze_firestore_patterns_tool = FunctionTool(func=analyze_firestore_patterns)
analyze_bq_usage_tool = FunctionTool(func=analyze_bq_usage)
estimate_cloud_costs_tool = FunctionTool(func=estimate_cloud_costs)


def _with_all_cloud_data(base_instruction: str):
    """Build dynamic instruction injecting all cloud analysis results from session state."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        data_parts = []
        for key in ("gcsAnalysis", "firestoreAnalysis", "bqAnalysis"):
            val = state.get(key)
            if val is not None:
                val_str = val if isinstance(val, str) else json.dumps(val)
                if len(val_str) > 15000:
                    val_str = val_str[:15000] + "\n...[truncated]"
                data_parts.append(f"--- {key} ---\n{val_str}")
        return f"{base_instruction}\n\n{''.join(data_parts)}" if data_parts else base_instruction

    return build_instruction


storage_analyzer = LlmAgent(
    name="StorageAnalyzer",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=STORAGE_ANALYZER_INSTRUCTION,
    tools=[analyze_gcs_usage_tool],
    output_key="gcsAnalysis",
)

firestore_analyzer = LlmAgent(
    name="FirestoreAnalyzer",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=FIRESTORE_ANALYZER_INSTRUCTION,
    tools=[analyze_firestore_patterns_tool],
    output_key="firestoreAnalysis",
)

bq_analyzer = LlmAgent(
    name="BigQueryAnalyzer",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=BQ_ANALYZER_INSTRUCTION,
    tools=[analyze_bq_usage_tool],
    output_key="bqAnalysis",
)

cloud_analysis_fan_out = ParallelAgent(
    name="CloudAnalysisFanOut",
    description="Analyzes GCS, Firestore, and BigQuery usage in parallel.",
    sub_agents=[storage_analyzer, firestore_analyzer, bq_analyzer],
)

cloud_recommender = LlmAgent(
    name="CloudCostRecommender",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=_with_all_cloud_data(CLOUD_RECOMMENDER_INSTRUCTION),
    tools=[estimate_cloud_costs_tool],
    output_key="cloudCostRecommendations",
)

cloud_cost_optimization_pipeline = SequentialAgent(
    name="CloudCostOptimizationPipeline",
    description="Analyzes GCS/Firestore/BQ in parallel, then synthesizes cost recommendations.",
    sub_agents=[cloud_analysis_fan_out, cloud_recommender],
)
