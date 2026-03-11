"""Discovery jobs endpoints — CRUD + run-now trigger.

GET  /api/admin/discovery-jobs               — list all jobs
POST /api/admin/discovery-jobs               — create a new job
GET  /api/admin/discovery-jobs/{id}          — get job detail
POST /api/admin/discovery-jobs/{id}/run-now  — immediately execute the Cloud Run Job
DELETE /api/admin/discovery-jobs/{id}        — cancel (pending) or delete
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.lib.auth import verify_admin_request

from hephae_db.firestore.discovery_jobs import (
    create_discovery_job,
    list_discovery_jobs,
    get_discovery_job,
    cancel_job,
    delete_discovery_job,
    STATUS_PENDING,
    STATUS_RUNNING,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/discovery-jobs", tags=["discovery-jobs"], dependencies=[Depends(verify_admin_request)])


class DiscoveryTargetInput(BaseModel):
    zipCode: str
    businessTypes: list[str] = []


class CreateJobRequest(BaseModel):
    name: str
    targets: list[DiscoveryTargetInput]
    notifyEmail: str = "admin@hephae.co"
    settings: dict = {}


@router.get("")
async def list_jobs():
    jobs = await list_discovery_jobs(limit=100)
    # Convert datetime objects to ISO strings for JSON serialization
    for job in jobs:
        for field in ("createdAt", "startedAt", "completedAt"):
            val = job.get(field)
            if val and hasattr(val, "isoformat"):
                job[field] = val.isoformat()
    return {"jobs": jobs}


@router.post("")
async def create_job(req: CreateJobRequest):
    if not req.targets:
        raise HTTPException(status_code=400, detail="targets must not be empty")

    targets = [t.model_dump() for t in req.targets]
    job_id = await create_discovery_job(
        name=req.name,
        targets=targets,
        notify_email=req.notifyEmail,
        settings=req.settings or None,
    )
    return {"success": True, "jobId": job_id}


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = await get_discovery_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field in ("createdAt", "startedAt", "completedAt"):
        val = job.get(field)
        if val and hasattr(val, "isoformat"):
            job[field] = val.isoformat()
    return job


@router.post("/{job_id}/run-now")
async def run_job_now(job_id: str):
    """Trigger an immediate execution of the discovery-batch Cloud Run Job.

    This executes the Cloud Run Job via the gcloud API, which will pick up
    the pending job from Firestore. The job must be in 'pending' status.
    """
    job = await get_discovery_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == STATUS_RUNNING:
        raise HTTPException(status_code=409, detail="Job is already running")
    if job["status"] not in (STATUS_PENDING,):
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be started from status: {job['status']}"
        )

    # Trigger the Cloud Run Job via gcloud CLI (available in Cloud Run environment)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    region = os.environ.get("CLOUD_RUN_REGION", "us-central1")
    job_name = "discovery-batch"

    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            "gcloud", "run", "jobs", "execute", job_name,
            "--region", region,
            "--project", project_id,
            "--async",  # don't wait for completion
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.error(f"[DiscoveryJobs] gcloud trigger failed: {err}")
            raise HTTPException(status_code=500, detail=f"Failed to trigger job: {err}")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=500, detail="Timed out triggering Cloud Run Job")

    logger.info(f"[DiscoveryJobs] Triggered Cloud Run Job for {job_id}")
    return {"success": True, "message": "Discovery batch job triggered. Check back in a few minutes."}


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    job = await get_discovery_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == STATUS_RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running job. Wait for it to complete or contact support."
        )

    if job["status"] == STATUS_PENDING:
        await cancel_job(job_id)
    else:
        await delete_discovery_job(job_id)

    return {"success": True}
