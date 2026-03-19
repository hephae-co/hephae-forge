"""Weekly Pulse admin endpoints — async job-based generation + CRUD.

POST /api/weekly-pulse           — Submit pulse generation job (returns immediately)
GET  /api/weekly-pulse/jobs/{id} — Poll job status
GET  /api/weekly-pulse           — List recent pulses
GET  /api/weekly-pulse/{zip}/{biz}/latest  — Latest pulse
GET  /api/weekly-pulse/{zip}/{biz}/history — Pulse history
GET  /api/weekly-pulse/id/{id}   — Specific pulse
DELETE /api/weekly-pulse/id/{id} — Delete pulse
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request
from hephae_api.routers.admin import _serialize
from hephae_db.firestore.weekly_pulse import (
    get_latest_pulse,
    get_pulse_by_id,
    get_pulse_history,
    list_pulses,
    delete_pulse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/weekly-pulse",
    tags=["weekly-pulse"],
    dependencies=[Depends(verify_admin_request)],
)


class GeneratePulseRequest(BaseModel):
    zipCode: str
    businessType: str
    weekOf: str = ""
    force: bool = False
    testMode: bool = False


async def _run_pulse_job(job_id: str, zip_code: str, business_type: str, week_of: str, force: bool, test_mode: bool = False):
    """Background task that runs the pulse pipeline and updates the job doc."""
    from hephae_db.firestore.pulse_jobs import update_pulse_job
    from hephae_api.workflows.orchestrators.weekly_pulse import generate_pulse

    try:
        await update_pulse_job(job_id, {
            "status": "RUNNING",
            "startedAt": datetime.utcnow(),
        })

        result = await generate_pulse(
            zip_code=zip_code,
            business_type=business_type,
            week_of=week_of,
            force=force,
            test_mode=test_mode,
        )

        await update_pulse_job(job_id, {
            "status": "COMPLETED",
            "completedAt": datetime.utcnow(),
            "result": {
                "pulseId": result["pulseId"],
                "signalsUsed": result["signalsUsed"],
                "insightCount": len(result.get("pulse", {}).get("insights", [])),
                "headline": result.get("pulse", {}).get("headline", ""),
                "diagnostics": result.get("diagnostics", {}),
            },
            "pipelineDetails": result.get("pipelineDetails", {}),
        })
        logger.info(f"[PulseJob] {job_id} completed — {result['pulseId']}")

    except Exception as e:
        logger.error(f"[PulseJob] {job_id} failed: {e}")
        await update_pulse_job(job_id, {
            "status": "FAILED",
            "completedAt": datetime.utcnow(),
            "error": str(e),
        })


@router.post("")
async def generate_weekly_pulse(req: GeneratePulseRequest):
    """Submit a pulse generation job. Returns immediately with a jobId."""
    if not re.match(r"^\d{5}$", req.zipCode):
        raise HTTPException(status_code=400, detail="Invalid zip code")
    if not req.businessType.strip():
        raise HTTPException(status_code=400, detail="businessType is required")

    from hephae_db.firestore.pulse_jobs import create_pulse_job

    week_of = req.weekOf or datetime.utcnow().strftime("%Y-%m-%d")

    job_id = await create_pulse_job(
        zip_code=req.zipCode,
        business_type=req.businessType,
        week_of=week_of,
        force=req.force,
        test_mode=req.testMode,
    )

    # Fire and forget — pipeline runs in background
    asyncio.create_task(_run_pulse_job(
        job_id, req.zipCode, req.businessType, week_of, req.force, req.testMode,
    ))

    return {
        "success": True,
        "jobId": job_id,
        "status": "QUEUED",
        "testMode": req.testMode,
    }


@router.get("/jobs/{job_id}")
async def get_pulse_job_status(job_id: str):
    """Poll job status. Returns result when COMPLETED."""
    from hephae_db.firestore.pulse_jobs import get_pulse_job

    job = await get_pulse_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response: dict = {
        "jobId": job["id"],
        "status": job["status"],
        "zipCode": job.get("zipCode", ""),
        "businessType": job.get("businessType", ""),
        "createdAt": job.get("createdAt"),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
    }

    if job["status"] == "COMPLETED" and job.get("result"):
        # Fetch the full pulse document for the response
        pulse_id = job["result"].get("pulseId")
        if pulse_id:
            pulse_doc = await get_pulse_by_id(pulse_id)
            if pulse_doc:
                response["pulse"] = _serialize(pulse_doc.get("pulse", {}))
                response["pulseId"] = pulse_id
                response["signalsUsed"] = job["result"].get("signalsUsed", [])
                response["diagnostics"] = job["result"].get("diagnostics", {})
        response["result"] = job["result"]
        response["pipelineDetails"] = job.get("pipelineDetails", {})

    if job["status"] == "FAILED":
        response["error"] = job.get("error", "Unknown error")

    return response


@router.get("")
async def list_all_pulses(limit: int = Query(20, ge=1, le=100)):
    """List all recent pulses across zip codes."""
    pulses = await list_pulses(limit=limit)
    return [_serialize(p) for p in pulses]


@router.get("/{zip_code}/{business_type}/latest")
async def get_latest(zip_code: str, business_type: str):
    """Get the most recent pulse for a zip code + business type."""
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    doc = await get_latest_pulse(zip_code, business_type)
    if not doc:
        raise HTTPException(status_code=404, detail="No pulse found")
    return _serialize(doc)


@router.get("/{zip_code}/{business_type}/history")
async def get_history(
    zip_code: str,
    business_type: str,
    limit: int = Query(8, ge=1, le=52),
):
    """Get historical pulses for a zip code + business type."""
    if not re.match(r"^\d{5}$", zip_code):
        raise HTTPException(status_code=400, detail="Invalid zip code")

    docs = await get_pulse_history(zip_code, business_type, limit=limit)
    return [_serialize(d) for d in docs]


@router.get("/id/{pulse_id}")
async def get_by_id(pulse_id: str):
    """Get a specific pulse by its document ID."""
    doc = await get_pulse_by_id(pulse_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pulse not found")
    return _serialize(doc)


@router.delete("/id/{pulse_id}")
async def delete_pulse_endpoint(pulse_id: str):
    """Delete a specific pulse."""
    await delete_pulse(pulse_id)
    return {"success": True}
