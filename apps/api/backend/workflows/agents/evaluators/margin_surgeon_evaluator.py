"""Margin Surgeon evaluator agent — validates restaurant profitability analysis."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from backend.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error

MarginSurgeonEvaluatorAgent = LlmAgent(
    name="margin_surgeon_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the Margin Surgeon for plausibility and hallucinations.",
    instruction="""You are an expert Restaurant Profitability QA system. Review the output from a Margin Analysis tool.
You will be given the BUSINESS_IDENTITY and the ACTUAL_OUTPUT JSON from the Margin Surgeon.
Validate that menu items are plausible for the business type, strategic advice is coherent, scores are consistent, and data isn't hallucinated.
Watch for red flags like sushi items for a pizza shop, impossible margins, or generic advice.

When FOOD_PRICING_CONTEXT is provided alongside the business identity, also verify:
- Strategic advice acknowledges current commodity cost trends
- Margin optimization suggestions are realistic given input cost changes
- Flag if advice recommends cost cuts on categories with >5% YoY increases without acknowledging the trend
- Award bonus score points if advice correctly references real cost data

Output MUST STRICTLY match this JSON schema:
{
    "score": number (0-100),
    "isHallucinated": boolean,
    "issues": string[]
}""",
    generate_content_config=ThinkingPresets.MEDIUM,
    on_model_error_callback=fallback_on_error,
)
