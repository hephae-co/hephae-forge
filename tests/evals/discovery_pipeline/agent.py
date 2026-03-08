"""Eval wrapper — re-exports discovery_pipeline as root_agent for ADK AgentEvaluator.

The discovery pipeline runs four stages:
  1. SiteCrawlerAgent: crawls the business URL
  2. DiscoveryFanOut: 8 specialized agents in parallel (theme, contact, social, menu, maps, etc.)
  3. SocialProfilerAgent: crawls discovered social profile URLs for metrics
  4. DiscoveryReviewerAgent: validates all URLs and cross-references data
"""

from hephae_capabilities.discovery.agent import discovery_pipeline as root_agent

__all__ = ["root_agent"]
