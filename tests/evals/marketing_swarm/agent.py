"""Eval wrapper — re-exports marketing_pipeline as root_agent for ADK AgentEvaluator."""

from hephae_agents.social.marketing_swarm.agent import marketing_pipeline as root_agent

__all__ = ["root_agent"]
