"""
Social Media Auditor agents — SocialResearcher + SocialStrategist.

Pipeline: Research each platform via google_search → Synthesize into scored audit.
"""

from google.adk.agents import LlmAgent

from backend.config import AgentModels, ThinkingPresets
from backend.lib.model_fallback import fallback_on_error
from backend.agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from backend.agents.social_media_auditor.prompts import (
    SOCIAL_RESEARCHER_INSTRUCTION,
    SOCIAL_STRATEGIST_INSTRUCTION,
)

social_researcher_agent = LlmAgent(
    name="SocialResearcherAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=SOCIAL_RESEARCHER_INSTRUCTION,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    on_model_error_callback=fallback_on_error,
)

social_strategist_agent = LlmAgent(
    name="SocialStrategistAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    instruction=SOCIAL_STRATEGIST_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)
