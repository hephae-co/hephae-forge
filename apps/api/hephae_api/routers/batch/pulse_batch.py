"""Batch pulse submission and status endpoints.

POST /api/cron/pulse-batch-submit  — Create batch work items + launch Cloud Run Job
GET  /api/cron/pulse-batch-status/{batch_id} — Check batch progress
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from hephae_api.lib.auth import verify_admin_request

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/cron",
    tags=["pulse-batch"],
    dependencies=[Depends(verify_admin_request)],
)


class PulseBatchRequest(BaseModel):
    county: str
    state: str
    businessType: str
    weekOf: str = ""


class PulseBatchResponse(BaseModel):
    success: bool
    batchId: str
    zipCount: int
    message: str = ""


@router.post("/pulse-batch-submit", response_model=PulseBatchResponse)
async def pulse_batch_submit(req: PulseBatchRequest):
    """Create work items for all zip codes in a county and launch batch job."""
    from hephae_db.bigquery.public_data import query_zips_in_county
    from hephae_db.firestore.pulse_batch import create_work_items

    # Resolve zip codes in county
    try:
        zips = await query_zips_in_county(req.county, req.state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to resolve zips: {e}")

    if not zips:
        raise HTTPException(status_code=404, detail=f"No zip codes found for {req.county}, {req.state}")

    # Generate batch ID
    now = datetime.utcnow()
    week_of = req.weekOf or f"{now.year}-W{now.isocalendar()[1]:02d}"
    county_slug = re.sub(r"[^a-z0-9]+", "-", req.county.lower().strip()).strip("-")
    batch_id = f"pulse-{county_slug}-{week_of}"

    # Create work items
    count = await create_work_items(batch_id, zips, req.businessType, week_of)

    # Launch Cloud Run Job
    try:
        from hephae_api.lib.job_launcher import launch_batch_job
        await launch_batch_job("pulse-batch", [batch_id])
        logger.info(f"[PulseBatch] Launched job for {batch_id} ({count} zips)")
    except Exception as e:
        logger.error(f"[PulseBatch] Failed to launch job: {e}")
        return PulseBatchResponse(
            success=True,
            batchId=batch_id,
            zipCount=count,
            message=f"Work items created but job launch failed: {e}. Run manually.",
        )

    return PulseBatchResponse(
        success=True,
        batchId=batch_id,
        zipCount=count,
        message=f"Batch {batch_id} submitted with {count} zip codes",
    )


@router.get("/pulse-batch-status/{batch_id}")
async def pulse_batch_status(batch_id: str):
    """Get batch progress summary."""
    from hephae_db.firestore.pulse_batch import get_batch_summary
    return await get_batch_summary(batch_id)
