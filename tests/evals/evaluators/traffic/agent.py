"""Eval wrapper — re-exports TrafficEvaluatorAgent as root_agent for ADK AgentEvaluator."""

from backend.workflows.agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent as root_agent

__all__ = ["root_agent"]
