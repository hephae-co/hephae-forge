"""Admin API for AI Tool Discovery.

GET    /api/ai-tool-discovery                        — List recent runs (all verticals or filtered)
GET    /api/ai-tool-discovery/tools/{vertical}       — Live tool list for a vertical (Firestore, fast)
GET    /api/ai-tool-discovery/{vertical}/latest      — Latest run for a vertical (BQ, full tools list)
GET    /api/ai-tool-discovery/{vertical}/{week_of}   — Specific run (BQ)
POST   /api/ai-tool-discovery/{vertical}/generate-now — Manual trigger
DELETE /api/ai-tool-discovery/{vertical}/{week_of}   — Delete a run
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request
from hephae_api.routers.admin import _serialize

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai-tool-discovery",
    tags=["ai-tool-discovery"],
    dependencies=[Depends(verify_admin_request)],
)


class GenerateRequest(BaseModel):
    force: bool = False
    testMode: bool = False


@router.get("")
async def list_runs(
    vertical: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent AI tool discovery runs (summaries only — no tools array)."""
    from hephae_db.bigquery.ai_tools import list_ai_tool_runs

    runs = await list_ai_tool_runs(vertical=vertical, limit=limit)
    return [_serialize(r) for r in runs]


@router.get("/tools/{vertical}")
async def get_tools_for_vertical(
    vertical: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Get current tools for a vertical from Firestore — fast serving layer.

    This is what the chat UI and blog writer should call, not the BQ endpoints.
    Returns tools ordered by popularity (weeksSeen desc).
    """
    from hephae_db.firestore.ai_tools import get_tools_for_vertical as _get

    tools = await _get(vertical=vertical, limit=limit)
    return [_serialize(t) for t in tools]


@router.get("/{vertical}/latest")
async def get_latest(vertical: str):
    """Get the most recent discovery run for a vertical (full tools list included)."""
    from hephae_db.bigquery.ai_tools import get_latest_ai_tool_run

    run = await get_latest_ai_tool_run(vertical)
    if not run:
        raise HTTPException(status_code=404, detail=f"No runs found for vertical '{vertical}'")
    return _serialize(run)


@router.get("/{vertical}/{week_of}")
async def get_run(vertical: str, week_of: str):
    """Get a specific run by vertical + week (full tools list included)."""
    from hephae_db.bigquery.ai_tools import get_ai_tool_run

    run = await get_ai_tool_run(vertical, week_of)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize(run)


@router.post("/{vertical}/generate-now")
async def generate_now(vertical: str, req: GenerateRequest):
    """Manually trigger AI tool discovery for a vertical."""
    from hephae_api.workflows.orchestrators.ai_tool_discovery import generate_ai_tool_discovery

    result = await generate_ai_tool_discovery(
        vertical=vertical,
        force=req.force,
        test_mode=req.testMode,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    if result.get("skipped"):
        return {
            "success": True,
            "skipped": True,
            "message": (
                f"Run already exists for {vertical}/{result.get('weekOf')}. "
                "Pass force=true to regenerate."
            ),
            "docId": result.get("id"),
        }

    return {
        "success": True,
        "docId": result["docId"],
        "weekOf": result["weekOf"],
        "totalToolsFound": result["totalToolsFound"],
        "newToolsCount": result["newToolsCount"],
        "highRelevanceCount": result["highRelevanceCount"],
        "freeToolsCount": result["freeToolsCount"],
        "weeklyHighlight": result.get("weeklyHighlight", {}),
    }


@router.delete("/{vertical}/{week_of}")
async def delete_run(vertical: str, week_of: str):
    """Delete a specific discovery run from BQ."""
    from hephae_db.bigquery.ai_tools import delete_ai_tool_run

    run_id = f"{vertical}-{week_of}"
    await delete_ai_tool_run(run_id)
    return {"success": True}
