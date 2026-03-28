"""Eval wrapper — re-exports social_post_parallel as root_agent for ADK AgentEvaluator.

Evaluates the ParallelAgent orchestrator that generates 5-channel outreach content
(Instagram, Facebook, Twitter, Email, Contact Form) for a given business.
"""

from hephae_agents.social.post_generator.agent import social_post_parallel as root_agent

__all__ = ["root_agent"]
