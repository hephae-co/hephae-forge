"""Sector research endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.lib.db.sector_research import load_sector_research, list_sector_research, get_sector_research_for_type
from backend.lib.db.area_research import get_area_research_for_zip_code
from backend.orchestrators.sector_research import run_sector_research

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sector-research", tags=["sector-research"])


class CreateSectorResearchRequest(BaseModel):
    sector: str
    zipCodes: list[str] | None = None
    areaName: str | None = None


@router.post("")
async def create_sector_research_endpoint(req: CreateSectorResearchRequest):
    zip_codes = req.zipCodes or []

    # If no zip codes provided, try to find from area research
    if not zip_codes and req.areaName:
        # Look up area research
        pass  # Will use zip codes from request

    # Check for existing completed research
    existing = await get_sector_research_for_type(req.sector)
    if existing:
        return {
            "sectorId": existing.id,
            "status": "existing",
            "sector": existing.sector,
        }

    # Run sector research in background
    asyncio.create_task(run_sector_research(req.sector, zip_codes, req.areaName))

    return {
        "status": "started",
        "sector": req.sector,
        "zipCodes": zip_codes,
    }


@router.get("")
async def list_sector_research_endpoint():
    docs = await list_sector_research(limit=20)
    return [d.model_dump(mode="json") for d in docs]


@router.get("/{sector_id}")
async def get_sector_research_endpoint(sector_id: str):
    doc = await load_sector_research(sector_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Sector research not found")
    return doc.model_dump(mode="json")
