"""Traffic evaluator agent — validates foot traffic forecast output."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas.agent_outputs import EvaluationOutput

TrafficEvaluatorAgent = LlmAgent(
    name="traffic_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the Traffic Forecaster for plausibility and hallucinations.",
    instruction="""You are an expert Foot Traffic & Location Analytics QA system. Review the output from a Traffic Forecast tool.
You will be given the BUSINESS_IDENTITY, the ACTUAL_OUTPUT JSON from the Traffic Forecaster, and optionally RESEARCH_CONTEXT with ground-truth weather/events data from admin research.

**Evaluation criteria (score 0-100):**
1. Geographic plausibility: business type, address, and nearby POIs make sense together
2. Time slot logic: scores align with business hours and day of week patterns
3. Weather consistency: weatherNote should be plausible for the location and season
4. Event relevance: localEvents should be real or plausible for the area
5. Score reasonability: traffic scores should reflect a realistic pattern (not all high, not all identical)

**Hallucination rules — be conservative:**
- ONLY flag isHallucinated=True if the output contains clearly fabricated data: invented addresses, impossible coordinates, business type contradictions, or events that could not plausibly exist in the area
- Do NOT flag as hallucinated just because you cannot independently verify a weather forecast or local event — the forecaster has access to real-time search tools you do not
- If RESEARCH_CONTEXT is provided, cross-check weather/event claims against it. Contradictions with research data ARE grounds for hallucination flags
- Minor inaccuracies (slightly off weather, generic events) should reduce the score but NOT trigger isHallucinated

Output MUST STRICTLY match this JSON schema:
{
    "score": number (0-100),
    "isHallucinated": boolean,
    "issues": string[]
}""",
    output_schema=EvaluationOutput,
    generate_content_config=ThinkingPresets.MEDIUM,
    on_model_error_callback=fallback_on_error,
)
