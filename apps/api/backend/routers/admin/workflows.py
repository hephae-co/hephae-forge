"""Workflow lifecycle endpoints — POST/GET /api/workflows, POST /api/workflows/county."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hephae_db.firestore.workflows import create_workflow, list_workflows
from backend.types import WorkflowDocument, WorkflowPhase, WorkflowProgress
from backend.workflows.engine import start_workflow_engine
from backend.workflows.agents.discovery.county_resolver import resolve_county_zip_codes

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    zipCode: str
    businessType: str | None = None


class CreateCountyWorkflowRequest(BaseModel):
    businessType: str
    county: str
    maxZipCodes: int | None = 10


@router.post("")
async def create_workflow_endpoint(req: CreateWorkflowRequest):
    if not req.zipCode or not re.match(r"^\d{5}$", req.zipCode):
        raise HTTPException(status_code=400, detail="Invalid zip code — must be 5 digits")

    workflow = await create_workflow(
        zip_code=req.zipCode, business_type=req.businessType,
        workflow_model=WorkflowDocument, phase_enum=WorkflowPhase, progress_model=WorkflowProgress,
    )

    # Start engine in background
    await start_workflow_engine(workflow.id)

    return {"workflowId": workflow.id, "status": "started"}


@router.get("")
async def list_workflows_endpoint():
    workflows = await list_workflows(limit=20, model_class=WorkflowDocument)
    return [w.model_dump(mode="json") for w in workflows]


@router.post("/county")
async def create_county_workflow(req: CreateCountyWorkflowRequest):
    max_zips = min(req.maxZipCodes or 10, 15)

    resolved = await resolve_county_zip_codes(req.county, max_zips)
    if not resolved.zipCodes:
        raise HTTPException(status_code=400, detail=resolved.error or "Could not resolve county")

    workflow = await create_workflow(
        zip_code=resolved.zipCodes[0],
        business_type=req.businessType,
        county=req.county,
        zip_codes=resolved.zipCodes,
        workflow_model=WorkflowDocument, phase_enum=WorkflowPhase, progress_model=WorkflowProgress,
    )

    await start_workflow_engine(workflow.id)

    return {
        "workflowId": workflow.id,
        "status": "started",
        "zipCodes": resolved.zipCodes,
        "countyName": resolved.countyName,
        "state": resolved.state,
    }
