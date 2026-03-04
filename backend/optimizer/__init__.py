"""
Optimizer module — meta-agents that analyze the codebase for optimization opportunities.

Four optimizer pipelines:
  1. Prompt Optimizer — improves agent prompts via Vertex AI Prompt Optimizer
  2. AI Cost Optimizer — recommends cheaper models and token reduction
  3. Cloud Cost Optimizer — analyzes GCS/Firestore/BQ usage patterns
  4. Performance Optimizer — identifies pipeline bottlenecks and concurrency improvements
"""

from backend.optimizer.orchestrator import run_optimizer
from backend.optimizer.prompt_optimizer import prompt_optimization_pipeline
from backend.optimizer.ai_cost_optimizer import ai_cost_optimization_pipeline
from backend.optimizer.cloud_cost_optimizer import cloud_cost_optimization_pipeline
from backend.optimizer.performance_optimizer import performance_optimization_pipeline
