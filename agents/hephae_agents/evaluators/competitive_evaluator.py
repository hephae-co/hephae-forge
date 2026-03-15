"""Competitive evaluator agent — validates competitive analysis output."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas.agent_outputs import EvaluationOutput

CompetitiveEvaluatorAgent = LlmAgent(
    name="competitive_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the Competitive Analyzer for accuracy and hallucinations.",
    instruction="""You are an expert Competitive Intelligence QA system. Review the output from a Competitive Analysis tool.
You will be given the BUSINESS_IDENTITY and the ACTUAL_OUTPUT JSON from the Competitive Analyzer.

**Evaluation criteria (score 0-100):**
1. Competitor plausibility: named competitors should be real businesses that could exist in the area
2. Analysis depth: pricing comparisons, market gaps, and positioning should be specific, not generic
3. Internal consistency: competitor details should align with the business type and location
4. Actionable insights: recommendations should be concrete and relevant

**Hallucination rules — be conservative:**
- ONLY flag isHallucinated=True if competitors are clearly fabricated (impossible names, wrong business type, contradictory locations) or if the analysis contains demonstrably false claims
- The competitive analyzer has access to Google Search — it can find real competitors you may not know about. Do NOT flag as hallucinated just because you cannot verify a competitor exists
- Generic or shallow analysis should reduce the score but NOT trigger isHallucinated
- If the analysis names specific real-sounding businesses in the correct geographic area with plausible details, assume they are real unless clearly contradicted

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
