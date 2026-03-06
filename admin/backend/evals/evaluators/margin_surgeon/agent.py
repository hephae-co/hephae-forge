"""Eval wrapper — re-exports MarginSurgeonEvaluatorAgent as root_agent for ADK AgentEvaluator."""

from backend.agents.evaluators.margin_surgeon_evaluator import MarginSurgeonEvaluatorAgent as root_agent

__all__ = ["root_agent"]
