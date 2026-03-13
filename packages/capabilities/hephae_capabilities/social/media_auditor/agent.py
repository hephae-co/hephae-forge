"""
Social Media Auditor agents — SocialResearcher + SocialStrategist as SequentialAgent.

Pipeline: Research each platform via google_search → Synthesize into scored audit.
"""

import json

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.load_memory_tool import load_memory_tool

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_capabilities.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_capabilities.social.media_auditor.prompts import (
    SOCIAL_RESEARCHER_INSTRUCTION,
    SOCIAL_STRATEGIST_INSTRUCTION,
)
from hephae_db.schemas.agent_outputs import SocialMediaAuditOutput


def _researcher_instruction(ctx):
    """Dynamic instruction — injects identity data from session state."""
    parts = [SOCIAL_RESEARCHER_INSTRUCTION]
    identity = ctx.state.get("identity", {})
    if identity.get("name"):
        parts.append(f"\n\nBusiness: {identity['name']}")
    if identity.get("address"):
        parts.append(f"Location: {identity['address']}")
    if identity.get("persona"):
        parts.append(f"Persona: {identity['persona']}")
    if identity.get("officialUrl"):
        parts.append(f"Website: {identity['officialUrl']}")
    social = identity.get("socialLinks") or {}
    active_social = {k: v for k, v in social.items() if v}
    if active_social:
        parts.append(f"\nKNOWN SOCIAL LINKS:\n{json.dumps(active_social, indent=2)}")
    spm = identity.get("socialProfileMetrics")
    if spm:
        parts.append(
            f"\nEXISTING DISCOVERY METRICS:\n{json.dumps(spm, default=str)[:3000]}"
        )
    competitors = identity.get("competitors", [])
    if competitors:
        parts.append(f"\nCOMPETITORS:\n{json.dumps(competitors[:5], default=str)}")
    return "\n".join(parts)


def _strategist_instruction(ctx):
    """Dynamic instruction — reads research brief + identity from session state."""
    parts = [SOCIAL_STRATEGIST_INSTRUCTION]
    identity = ctx.state.get("identity", {})
    if identity:
        parts.append(f"\n\nTARGET BUSINESS: {json.dumps(identity, default=str)[:4000]}")
    brief = ctx.state.get("researchBrief", "")
    if brief:
        parts.append(f"\n\nSOCIAL MEDIA RESEARCH BRIEF:\n{brief}")
    parts.append("\n\nGenerate the final social media audit JSON report.")
    return "\n".join(parts)


social_researcher_agent = LlmAgent(
    name="SocialResearcherAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=_researcher_instruction,
    output_key="researchBrief",
    tools=[google_search_tool, crawl4ai_advanced_tool, load_memory_tool],
    on_model_error_callback=fallback_on_error,
)

social_strategist_agent = LlmAgent(
    name="SocialStrategistAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    instruction=_strategist_instruction,
    output_schema=SocialMediaAuditOutput,
    on_model_error_callback=fallback_on_error,
)

social_audit_pipeline = SequentialAgent(
    name="SocialAuditPipeline",
    description="2-stage social media audit: research platforms → synthesize strategy.",
    sub_agents=[social_researcher_agent, social_strategist_agent],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)
