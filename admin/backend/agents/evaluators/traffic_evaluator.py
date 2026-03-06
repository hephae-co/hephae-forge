"""Traffic evaluator agent — validates foot traffic forecast output."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from backend.config import AgentModels, ThinkingPresets
from backend.lib.model_fallback import fallback_on_error

TrafficEvaluatorAgent = LlmAgent(
    name="traffic_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the Traffic Forecaster for plausibility and hallucinations.",
    instruction="""You are an expert Foot Traffic & Location Analytics QA system. Review the output from a Traffic Forecast tool.
You will be given the BUSINESS_IDENTITY and the ACTUAL_OUTPUT JSON from the Traffic Forecaster.
Validate that the forecast is geographically plausible, the time slots make sense, and the data isn't hallucinated.

Output MUST STRICTLY match this JSON schema:
{
    "score": number (0-100),
    "isHallucinated": boolean,
    "issues": string[]
}""",
    generate_content_config=ThinkingPresets.MEDIUM,
    on_model_error_callback=fallback_on_error,
)
