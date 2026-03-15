"""Test fixtures endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request

from hephae_db.firestore.fixtures import save_fixture, list_fixtures, get_fixture, delete_fixture
from hephae_db.firestore.workflows import load_workflow
from hephae_api.types import WorkflowDocument
from hephae_api.routers.admin import _serialize

router = APIRouter(prefix="/api/fixtures", tags=["fixtures"], dependencies=[Depends(verify_admin_request)])


class CreateFixtureRequest(BaseModel):
    workflowId: str
    businessSlug: str
    fixtureType: str  # "grounding" | "failure_case"
    notes: str | None = None


@router.post("")
async def create_fixture(req: CreateFixtureRequest):
    workflow = await load_workflow(req.workflowId, model_class=WorkflowDocument)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    biz = next((b for b in workflow.businesses if b.slug == req.businessSlug), None)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found in workflow")

    from hephae_db.firestore.businesses import get_business
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
    return [_serialize(f) for f in fixtures]


@router.get("/{fixture_id}")
async def get_fixture_endpoint(fixture_id: str):
    fixture = await get_fixture(fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return _serialize(fixture)


@router.delete("/{fixture_id}")
async def delete_fixture_endpoint(fixture_id: str):
    await delete_fixture(fixture_id)
    return {"success": True}
