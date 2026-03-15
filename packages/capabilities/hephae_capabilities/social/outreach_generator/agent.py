"""Outreach Generator Agent — generates personalized marketing content."""

from google.adk.agents import LlmAgent
from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from .prompts import OUTREACH_GENERATOR_INSTRUCTION

OutreachGeneratorAgent = LlmAgent(
    name="OutreachGenerator",
    model=AgentModels.PRIMARY_MODEL,
    instruction=OUTREACH_GENERATOR_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)
