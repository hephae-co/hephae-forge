"""AI Cost Optimizer — 3-stage pipeline analyzing model usage and recommending cost savings."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from backend.config import AgentModels
from backend.lib.model_fallback import fallback_on_error
from backend.optimizer.ai_cost_optimizer.prompts import (
    MODEL_USAGE_ANALYZER_INSTRUCTION,
    TOKEN_ANALYZER_INSTRUCTION,
    COST_RECOMMENDER_INSTRUCTION,
)
from backend.optimizer.ai_cost_optimizer.tools import (
    scan_agent_configs,
    estimate_token_usage,
    calculate_cost_savings,
)

scan_agent_configs_tool = FunctionTool(func=scan_agent_configs)
estimate_token_usage_tool = FunctionTool(func=estimate_token_usage)
calculate_cost_savings_tool = FunctionTool(func=calculate_cost_savings)


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


model_usage_analyzer = LlmAgent(
    name="ModelUsageAnalyzer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=MODEL_USAGE_ANALYZER_INSTRUCTION,
    tools=[scan_agent_configs_tool],
    output_key="modelUsageReport",
    on_model_error_callback=fallback_on_error,
)

token_analyzer = LlmAgent(
    name="TokenAnalyzer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_prior_data(TOKEN_ANALYZER_INSTRUCTION, "modelUsageReport"),
    tools=[estimate_token_usage_tool],
    output_key="tokenAnalysis",
    on_model_error_callback=fallback_on_error,
)

cost_recommender = LlmAgent(
    name="CostRecommender",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_with_prior_data(COST_RECOMMENDER_INSTRUCTION, "modelUsageReport", "tokenAnalysis"),
    tools=[calculate_cost_savings_tool],
    output_key="aiCostRecommendations",
    on_model_error_callback=fallback_on_error,
)

ai_cost_optimization_pipeline = SequentialAgent(
    name="AICostOptimizationPipeline",
    description="Analyzes model usage, estimates token costs, and recommends optimizations.",
    sub_agents=[model_usage_analyzer, token_analyzer, cost_recommender],
)
