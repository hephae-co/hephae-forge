"""Test runner endpoints — POST/GET /api/run-tests."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.services.test_runner import test_runner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/run-tests", tags=["test-runner"])


@router.post("")
async def run_tests():
    try:
        summary = await test_runner.run_all_tests()
        return summary
    except Exception as e:
        logger.error(f"[TestRunner] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_test_runs():
    # Historical test runs
    return []
