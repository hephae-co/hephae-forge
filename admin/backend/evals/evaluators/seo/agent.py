"""Eval wrapper — re-exports SeoEvaluatorAgent as root_agent for ADK AgentEvaluator."""

from backend.agents.evaluators.seo_evaluator import SeoEvaluatorAgent as root_agent

__all__ = ["root_agent"]
