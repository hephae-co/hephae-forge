"""Eval wrapper — re-exports discovery_pipeline as root_agent for ADK AgentEvaluator.

The discovery pipeline runs five stages:
  1. SiteCrawlerAgent: crawls the business URL (with deterministic contact extraction)
  2. EntityMatcherAgent: validates the crawled site matches the target business
  3. DiscoveryFanOut: 9 specialized agents in parallel (theme, contact, social, menu, maps, challenges, etc.)
  4. SocialProfilerAgent: crawls discovered social profile URLs for metrics
  5. DiscoveryReviewerAgent: validates all URLs and cross-references data
"""

from hephae_agents.discovery.agent import discovery_pipeline as root_agent

__all__ = ["root_agent"]
