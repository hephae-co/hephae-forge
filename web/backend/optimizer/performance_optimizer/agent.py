"""Performance Optimizer — 3-stage pipeline analyzing bottlenecks and concurrency."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from backend.config import AgentModels
from backend.lib.model_fallback import fallback_on_error
from backend.optimizer.performance_optimizer.prompts import (
    PIPELINE_ANALYZER_INSTRUCTION,
    BOTTLENECK_DETECTOR_INSTRUCTION,
    CONCURRENCY_RECOMMENDER_INSTRUCTION,
)
from backend.optimizer.performance_optimizer.tools import (
    scan_pipeline_structure,
    detect_bottlenecks,
    analyze_async_patterns,
)

scan_pipeline_structure_tool = FunctionTool(func=scan_pipeline_structure)
detect_bottlenecks_tool = FunctionTool(func=detect_bottlenecks)
analyze_async_patterns_tool = FunctionTool(func=analyze_async_patterns)


def _with_prior_data(base_instruction: str, *keys: str):
    """Build dynamic instruction injecting prior stage outputs from session state."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        data_parts = []
        for key in keys:
            val = state.get(key)
            if val is not None:
                val_str = val if isinstance(val, str) else json.dumps(val)
                if len(val_str) > 20000:
                    val_str = val_str[:20000] + "\n...[truncated]"
                data_parts.append(f"--- {key} ---\n{val_str}")
        return f"{base_instruction}\n\n{''.join(data_parts)}" if data_parts else base_instruction

    return build_instruction


pipeline_analyzer = LlmAgent(
    name="PipelineAnalyzer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=PIPELINE_ANALYZER_INSTRUCTION,
    tools=[scan_pipeline_structure_tool],
    output_key="pipelineAnalysis",
    on_model_error_callback=fallback_on_error,
)

bottleneck_detector = LlmAgent(
    name="BottleneckDetector",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_prior_data(BOTTLENECK_DETECTOR_INSTRUCTION, "pipelineAnalysis"),
    tools=[detect_bottlenecks_tool],
    output_key="bottleneckReport",
    on_model_error_callback=fallback_on_error,
)

concurrency_recommender = LlmAgent(
    name="ConcurrencyRecommender",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_prior_data(CONCURRENCY_RECOMMENDER_INSTRUCTION, "pipelineAnalysis", "bottleneckReport"),
    tools=[analyze_async_patterns_tool],
    output_key="performanceRecommendations",
    on_model_error_callback=fallback_on_error,
)

performance_optimization_pipeline = SequentialAgent(
    name="PerformanceOptimizationPipeline",
    description="Analyzes pipeline topology, detects bottlenecks, and recommends concurrency improvements.",
    sub_agents=[pipeline_analyzer, bottleneck_detector, concurrency_recommender],
)
