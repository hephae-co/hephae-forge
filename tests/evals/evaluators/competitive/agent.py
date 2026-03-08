"""Eval wrapper — re-exports CompetitiveEvaluatorAgent as root_agent for ADK AgentEvaluator."""

from backend.workflows.agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent as root_agent

__all__ = ["root_agent"]
