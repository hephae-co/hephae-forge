"""Eval wrapper — re-exports ZipcodeScannerAgent as root_agent for ADK AgentEvaluator."""

from backend.workflows.agents.discovery.zipcode_scanner import ZipcodeScannerAgent as root_agent

__all__ = ["root_agent"]
