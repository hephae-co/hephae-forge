"""Eval wrapper — constructs a ProfileBuilderAgent as root_agent for ADK AgentEvaluator.

The profile builder agent is assembled at runtime in the router, so we construct
a standalone eval instance here using the shared instruction.
"""

from google.adk.agents import LlmAgent

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.profile_builder.agent import PROFILE_BUILDER_INSTRUCTION

root_agent = LlmAgent(
    name="profile_builder",
    model=AgentModels.PRIMARY_MODEL,
    description="Guides business owners through profile setup via multi-turn conversation.",
    instruction=PROFILE_BUILDER_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)

__all__ = ["root_agent"]
