"""Eval wrapper — re-exports CommunicatorAgent as root_agent for ADK AgentEvaluator."""

from backend.agents.outreach.communicator import CommunicatorAgent as root_agent

__all__ = ["root_agent"]
