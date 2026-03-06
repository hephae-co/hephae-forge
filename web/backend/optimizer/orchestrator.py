"""OptimizerOrchestrator — runs all 4 or individual optimizer pipelines."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from backend.lib.adk_helpers import user_msg

logger = logging.getLogger(__name__)


async def _run_pipeline(pipeline, prompt_text: str, output_key: str) -> dict:
    """Run a single optimizer pipeline and return its output from session state."""
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="hephae-optimizer",
        agent=pipeline,
        session_service=session_service,
    )

    session_id = f"opt-{int(time.time() * 1000)}"
    user_id = "optimizer"

    await session_service.create_session(
        app_name="hephae-optimizer",
        user_id=user_id,
        session_id=session_id,
        state={},
    )

    async for _ in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(prompt_text),
    ):
        pass

    session = await session_service.get_session(
        app_name="hephae-optimizer", user_id=user_id, session_id=session_id
    )
    state = session.state if session else {}

    raw = state.get(output_key, "{}")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            import re
            cleaned = re.sub(r"```json\n?|\n?```", "", raw).strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return {"raw_output": raw}
    return {}


async def _run_prompt_optimizer() -> dict:
    from backend.optimizer.prompt_optimizer import prompt_optimization_pipeline

    return await _run_pipeline(
        prompt_optimization_pipeline,
        "Scan all agent prompts in the codebase and optimize them using Vertex AI Prompt Optimizer.",
        "promptOptimizationResults",
    )


async def _run_ai_cost_optimizer() -> dict:
    from backend.optimizer.ai_cost_optimizer import ai_cost_optimization_pipeline

    return await _run_pipeline(
        ai_cost_optimization_pipeline,
        "Analyze all agent model configurations and recommend cost optimizations.",
        "aiCostRecommendations",
    )


async def _run_cloud_cost_optimizer() -> dict:
    from backend.optimizer.cloud_cost_optimizer import cloud_cost_optimization_pipeline

    return await _run_pipeline(
        cloud_cost_optimization_pipeline,
        "Analyze GCS, Firestore, and BigQuery usage patterns and recommend cost optimizations.",
        "cloudCostRecommendations",
    )


async def _run_performance_optimizer() -> dict:
    from backend.optimizer.performance_optimizer import performance_optimization_pipeline

    return await _run_pipeline(
        performance_optimization_pipeline,
        "Analyze all agent pipelines for bottlenecks and recommend performance improvements.",
        "performanceRecommendations",
    )


async def run_optimizer(optimizers: list[str] | None = None) -> dict:
    """Run specified optimizers and return aggregated results.

    Args:
        optimizers: List of optimizer names to run. Defaults to ["all"].
            Valid values: "all", "prompt", "ai_cost", "cloud_cost", "performance"

    Returns:
        dict with results keyed by optimizer name, plus run_at and duration_seconds.
    """
    if optimizers is None:
        optimizers = ["all"]

    run_all = "all" in optimizers
    start = time.time()
    results: dict = {}

    if run_all or "prompt" in optimizers:
        try:
            results["prompt_optimization"] = await _run_prompt_optimizer()
        except Exception as e:
            logger.error(f"[Optimizer] Prompt optimizer failed: {e}")
            results["prompt_optimization"] = {"error": str(e)}

    if run_all or "ai_cost" in optimizers:
        try:
            results["ai_cost_optimization"] = await _run_ai_cost_optimizer()
        except Exception as e:
            logger.error(f"[Optimizer] AI cost optimizer failed: {e}")
            results["ai_cost_optimization"] = {"error": str(e)}

    if run_all or "cloud_cost" in optimizers:
        try:
            results["cloud_cost_optimization"] = await _run_cloud_cost_optimizer()
        except Exception as e:
            logger.error(f"[Optimizer] Cloud cost optimizer failed: {e}")
            results["cloud_cost_optimization"] = {"error": str(e)}

    if run_all or "performance" in optimizers:
        try:
            results["performance_optimization"] = await _run_performance_optimizer()
        except Exception as e:
            logger.error(f"[Optimizer] Performance optimizer failed: {e}")
            results["performance_optimization"] = {"error": str(e)}

    results["run_at"] = datetime.now(timezone.utc).isoformat()
    results["duration_seconds"] = round(time.time() - start, 2)

    return results
