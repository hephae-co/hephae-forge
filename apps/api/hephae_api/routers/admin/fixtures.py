"""Test fixtures endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request

from hephae_db.firestore.fixtures import save_fixture, list_fixtures, get_fixture, delete_fixture
from hephae_api.routers.admin import _serialize

router = APIRouter(prefix="/api/fixtures", tags=["fixtures"], dependencies=[Depends(verify_admin_request)])


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
