"""Eval wrapper — exposes BusinessOverviewSynthesizer as root_agent for ADK AgentEvaluator.

Uses the synthesizer agent directly (reads searchResults, mapsData, and context
from session state) to evaluate the core synthesis capability without requiring
live Firestore/BigQuery calls.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.business_overview.agent import SYNTHESIZER_INSTRUCTION

root_agent = LlmAgent(
    name="business_overview_synthesizer",
    model=AgentModels.PRIMARY_MODEL,
    description="Synthesizes business research into a structured overview.",
    instruction=SYNTHESIZER_INSTRUCTION,
    tools=[google_search],
    output_key="overview",
    on_model_error_callback=fallback_on_error,
)

__all__ = ["root_agent"]
