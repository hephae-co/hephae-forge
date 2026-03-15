"""Test runner endpoints — POST/GET /api/run-tests.

POST: Runs the full QA suite (4 capabilities × evaluators), persists to Firestore.
GET:  Returns historical test runs (newest first, 7-day TTL auto-cleanup).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from hephae_api.lib.auth import verify_admin_request
from hephae_api.workflows.test_runner import test_runner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/run-tests", tags=["test-runner"], dependencies=[Depends(verify_admin_request)])


@router.post("")
async def run_tests():
    try:
        summary = await test_runner.run_all_tests()
        return summary
    except Exception as e:
        logger.error(f"[TestRunner] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_test_runs(limit: int = Query(20, ge=1, le=100)):
    """Return historical test runs from Firestore (auto-cleaned after 7 days)."""
    try:
        from hephae_db.firestore.test_runs import list_test_runs
        runs = await list_test_runs(limit=limit)
        return runs
    except Exception as e:
        logger.warning(f"[TestRunner] Failed to fetch history: {e}")
        return []
