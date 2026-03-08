"""Eval wrapper — re-exports seo_auditor_agent as root_agent for ADK AgentEvaluator."""

from hephae_capabilities.seo_auditor.agent import seo_auditor_agent as root_agent

__all__ = ["root_agent"]
