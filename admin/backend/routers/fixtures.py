"""Test fixtures endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.lib.db.fixtures import save_fixture, list_fixtures, get_fixture, delete_fixture
from backend.lib.db.workflows import load_workflow

router = APIRouter(prefix="/api/fixtures", tags=["fixtures"])


class CreateFixtureRequest(BaseModel):
    workflowId: str
    businessSlug: str
    fixtureType: str  # "grounding" | "failure_case"
    notes: str | None = None


@router.post("")
async def create_fixture(req: CreateFixtureRequest):
    workflow = await load_workflow(req.workflowId)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    biz = next((b for b in workflow.businesses if b.slug == req.businessSlug), None)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found in workflow")

    from backend.lib.db.businesses import get_business
    biz_data = await get_business(req.businessSlug)

    fixture_id = await save_fixture(
        workflow_id=req.workflowId,
        business_slug=req.businessSlug,
        fixture_type=req.fixtureType,
        notes=req.notes,
        business_state=biz.model_dump(mode="json"),
        identity={
            "name": biz.name,
            "address": biz.address,
            "docId": req.businessSlug,
        },
        latest_outputs=(biz_data or {}).get("latestOutputs", {}),
        source_zip_code=biz.sourceZipCode,
        business_type=biz.businessType,
    )

    return {"success": True, "fixtureId": fixture_id}


@router.get("")
async def list_fixtures_endpoint(type: str | None = Query(None)):
    fixtures = await list_fixtures(fixture_type=type)
    return [f.model_dump(mode="json") for f in fixtures]


@router.get("/{fixture_id}")
async def get_fixture_endpoint(fixture_id: str):
    fixture = await get_fixture(fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return fixture.model_dump(mode="json")


@router.delete("/{fixture_id}")
async def delete_fixture_endpoint(fixture_id: str):
    await delete_fixture(fixture_id)
    return {"success": True}
