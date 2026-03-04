"""
DEPRECATED — This module is superseded by the standalone `hephae-optimizer` MCP server.

Use `hephae-optimizer` instead:
  - Location: /Users/sarthak/Desktop/hephae/hephae-optimizer/
  - Install: pip install -e /Users/sarthak/Desktop/hephae/hephae-optimizer/
  - MCP config: .mcp.json at project root
  - Works on any Python project (AST-based scanning, no importlib)

This module is kept for backward compatibility but will be removed in a future release.
"""

from backend.optimizer.orchestrator import run_optimizer
from backend.optimizer.prompt_optimizer import prompt_optimization_pipeline
from backend.optimizer.ai_cost_optimizer import ai_cost_optimization_pipeline
from backend.optimizer.cloud_cost_optimizer import cloud_cost_optimization_pipeline
from backend.optimizer.performance_optimizer import performance_optimization_pipeline
