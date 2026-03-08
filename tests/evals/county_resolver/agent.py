"""Eval wrapper — re-exports CountyResolverAgent as root_agent for ADK AgentEvaluator."""

from backend.workflows.agents.discovery.county_resolver import CountyResolverAgent as root_agent

__all__ = ["root_agent"]
