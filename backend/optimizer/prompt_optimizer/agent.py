"""Prompt Optimizer — 2-stage pipeline scanning and optimizing agent prompts."""

from __future__ import annotations

import json

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from backend.config import AgentModels
from backend.optimizer.prompt_optimizer.prompts import (
    PROMPT_SCANNER_INSTRUCTION,
    PROMPT_OPTIMIZER_INSTRUCTION,
)
from backend.optimizer.prompt_optimizer.tools import (
    list_all_prompts,
    optimize_prompt_vertex,
    compare_prompt_quality,
)

list_all_prompts_tool = FunctionTool(func=list_all_prompts)
optimize_prompt_vertex_tool = FunctionTool(func=optimize_prompt_vertex)
compare_prompt_quality_tool = FunctionTool(func=compare_prompt_quality)


def _with_scan_results(base_instruction: str):
    """Build dynamic instruction injecting scan results from session state."""

    def build_instruction(context) -> str:
        state = getattr(context, "state", {})
        scan = state.get("promptScanResults")
        if scan is None:
            return base_instruction
        scan_str = scan if isinstance(scan, str) else json.dumps(scan)
        if len(scan_str) > 20000:
            scan_str = scan_str[:20000] + "\n...[truncated]"
        return f"{base_instruction}\n\n--- SCAN RESULTS ---\n{scan_str}"

    return build_instruction


prompt_scanner_agent = LlmAgent(
    name="PromptScannerAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,
    instruction=PROMPT_SCANNER_INSTRUCTION,
    tools=[list_all_prompts_tool],
    output_key="promptScanResults",
)

prompt_optimizer_agent = LlmAgent(
    name="PromptOptimizerAgent",
    model=AgentModels.DEEP_ANALYST_MODEL,
    instruction=_with_scan_results(PROMPT_OPTIMIZER_INSTRUCTION),
    tools=[optimize_prompt_vertex_tool, compare_prompt_quality_tool],
    output_key="promptOptimizationResults",
)

prompt_optimization_pipeline = SequentialAgent(
    name="PromptOptimizationPipeline",
    description="Scans all prompts in the codebase, then optimizes each using Vertex AI Prompt Optimizer.",
    sub_agents=[prompt_scanner_agent, prompt_optimizer_agent],
)
