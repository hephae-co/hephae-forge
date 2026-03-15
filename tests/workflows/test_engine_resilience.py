"""
Engine Resilience & Fault Tolerance — Tier 4 Evals.

Validates that the WorkflowEngine handles agent failures, 
persists state correctly, and supports resuming from failure.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from hephae_api.workflows.engine import WorkflowEngine
from hephae_db.firestore.workflows import WorkflowDocument
from hephae_common.models import WorkflowPhase, BusinessPhase

@pytest.mark.asyncio
async def test_engine_handles_agent_failure_and_resumes():
    """Verify that a failed agent transition allows for a subsequent successful resume."""
    workflow_id = "resilience-test-wf"
    
    # Mocking WorkflowDocument with 1 business
    mock_biz = AsyncMock()
    mock_biz.slug = "fail-biz"
    mock_biz.phase = BusinessPhase.PENDING
    
    mock_workflow = AsyncMock(spec=WorkflowDocument)
    mock_workflow.id = workflow_id
    mock_workflow.phase = WorkflowPhase.DISCOVERY
    mock_workflow.businesses = [mock_biz]
    
    # 1. Simulate Failure
    # We patch the discovery phase to raise an exception
    with patch("hephae_api.workflows.phases.discovery.run_discovery_phase", side_effect=Exception("Gemini Timeout")):
        engine = WorkflowEngine(mock_workflow)
        await engine.run()
        
        # Verify workflow transitioned to failed
        assert mock_workflow.phase == WorkflowPhase.FAILED
        assert "Gemini Timeout" in (mock_workflow.last_error or "")

    # 2. Simulate Resume
    # Now patch discovery to SUCCEED
    mock_workflow.phase = WorkflowPhase.DISCOVERY # Reset phase for resume
    
    with patch("hephae_api.workflows.phases.discovery.run_discovery_phase", new_callable=AsyncMock) as mock_discovery:
        engine = WorkflowEngine(mock_workflow)
        await engine.run()
        
        # Verify discovery was called again
        mock_discovery.assert_called_once()
        # Verify workflow completed discovery and moved to analysis
        assert mock_workflow.phase == WorkflowPhase.ANALYSIS

@pytest.mark.asyncio
async def test_engine_skips_completed_businesses_on_resume():
    """Verify that businesses in 'ANALYSIS_DONE' are not re-analyzed on resume."""
    workflow_id = "skip-test-wf"
    
    biz_done = AsyncMock()
    biz_done.slug = "already-done"
    biz_done.phase = BusinessPhase.ANALYSIS_DONE
    
    biz_pending = AsyncMock()
    biz_pending.slug = "needs-analysis"
    biz_pending.phase = BusinessPhase.PENDING
    
    mock_workflow = AsyncMock(spec=WorkflowDocument)
    mock_workflow.id = workflow_id
    mock_workflow.phase = WorkflowPhase.ANALYSIS
    mock_workflow.businesses = [biz_done, biz_pending]
    
    # Patch the analysis executor (Cloud Tasks enqueue)
    with patch("hephae_api.workflows.phases.analysis.enqueue_analysis_task", new_callable=AsyncMock) as mock_enqueue:
        engine = WorkflowEngine(mock_workflow)
        await engine.run()
        
        # Should only be called for the pending business
        assert mock_enqueue.call_count == 1
        assert mock_enqueue.call_args[0][0] == "needs-analysis"
