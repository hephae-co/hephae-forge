"""POST /api/optimize — Run optimizer agents.

DEPRECATED: This router is superseded by the hephae-optimizer MCP server.
Use the MCP tools (scan_prompts, analyze_all, etc.) via Claude Code instead.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.optimizer.orchestrator import (
    run_optimizer,
    _run_prompt_optimizer,
    _run_ai_cost_optimizer,
    _run_cloud_cost_optimizer,
    _run_performance_optimizer,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/optimize")
async def optimize(request: Request):
    """Run all or specified optimizers.

    Body: {"optimizers": ["all"]} or {"optimizers": ["prompt", "ai_cost"]}
    """
    try:
        body = await request.json()
        optimizers = body.get("optimizers", ["all"])
        result = await run_optimizer(optimizers)
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[Optimizer API] Failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/optimize/prompt")
async def optimize_prompt(request: Request):
    """Run only the prompt optimizer."""
    try:
        result = await _run_prompt_optimizer()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[Optimizer API] Prompt optimizer failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/optimize/ai-cost")
async def optimize_ai_cost(request: Request):
    """Run only the AI cost optimizer."""
    try:
        result = await _run_ai_cost_optimizer()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[Optimizer API] AI cost optimizer failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/optimize/cloud-cost")
async def optimize_cloud_cost(request: Request):
    """Run only the cloud cost optimizer."""
    try:
        result = await _run_cloud_cost_optimizer()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[Optimizer API] Cloud cost optimizer failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/optimize/performance")
async def optimize_performance(request: Request):
    """Run only the performance optimizer."""
    try:
        result = await _run_performance_optimizer()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[Optimizer API] Performance optimizer failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
