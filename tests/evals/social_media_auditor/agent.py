"""Eval wrapper — wraps social_researcher_agent + social_strategist_agent in a
SequentialAgent for ADK AgentEvaluator.

The social media auditor runs two LlmAgents sequentially:
  1. SocialResearcherAgent: researches social media presence via Google Search + crawl4ai
  2. SocialStrategistAgent: synthesizes findings into a scored audit + strategy
"""

from google.adk.agents import SequentialAgent

from hephae_agents.social.media_auditor.agent import (
    social_researcher_agent,
    social_strategist_agent,
)

root_agent = SequentialAgent(
    name="SocialMediaAuditPipeline",
    description="Full social media audit: research presence then synthesize strategy.",
    sub_agents=[social_researcher_agent, social_strategist_agent],
)

__all__ = ["root_agent"]
