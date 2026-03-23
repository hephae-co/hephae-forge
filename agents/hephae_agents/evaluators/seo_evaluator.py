"""SEO evaluator agent — validates SEO audit output quality."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas.agent_outputs import EvaluationOutput

SeoEvaluatorAgent = LlmAgent(
    name="seo_evaluator",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the output of the SEO Auditor for completeness and hallucinations.",
    instruction="""You are an expert SEO Quality Assurance system. Your job is to review the output from an SEO Audit tool for a specific business URL.
You will be given the TARGET_URL and the ACTUAL_OUTPUT JSON from the SEO Auditor.
Evaluate if the output is coherent, actually belongs to the given URL, and properly describes SEO aspects without hallucinating.

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
