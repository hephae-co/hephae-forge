"""Competitive evaluator agent — validates competitive analysis output."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from backend.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas.agent_outputs import EvaluationOutput

CompetitiveEvaluatorAgent = LlmAgent(
    name="competitive_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the Competitive Analyzer for accuracy and hallucinations.",
    instruction="""You are an expert Competitive Intelligence QA system. Review the output from a Competitive Analysis tool.
You will be given the BUSINESS_IDENTITY and the ACTUAL_OUTPUT JSON from the Competitive Analyzer.
Verify that competitors are real, pricing/gaps analysis is reasonable, and the data isn't hallucinated.

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
