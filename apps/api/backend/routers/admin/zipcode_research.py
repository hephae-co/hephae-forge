"""Zip code research endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.lib.auth import verify_admin_request

from hephae_db.firestore.research import (
    get_zipcode_report, get_run, delete_run, list_zipcode_runs,
)
from backend.workflows.orchestrators.zipcode_research import research_zip_code
from backend.routers.admin import _serialize

router = APIRouter(prefix="/api/zipcode-research", tags=["zipcode-research"], dependencies=[Depends(verify_admin_request)])


@router.get("")
async def list_runs(limit: int = Query(10, ge=1, le=50)):
    runs = await list_zipcode_runs(limit=limit)
    return [_serialize(r) for r in runs]


@router.post("/{zip_code}")
async def start_research(zip_code: str, force: bool = Query(False)):
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    result = await research_zip_code(zip_code, force=force)
    return {"success": True, "report": result["report"], "runId": result["runId"]}


@router.get("/{zip_code}")
async def get_report(zip_code: str):
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    doc = await get_zipcode_report(zip_code)
    if not doc:
        raise HTTPException(status_code=404, detail="No report found")

    return _serialize(doc)


@router.get("/runs/{run_id}")
async def get_run_endpoint(run_id: str):
    doc = await get_run(run_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize(doc)


@router.delete("/runs/{run_id}")
async def delete_run_endpoint(run_id: str):
    await delete_run(run_id)
    return {"success": True}
