"""Comprehensive tests for the Cloud Tasks workflow pipeline.

Covers:
1. enqueue_agent_task — payload construction, OIDC, error handling
2. get_tasks_by_ids — batch fetch from Firestore
3. run_analysis_phase — enqueue + poll loop + callback firing
4. _run_workflow_analyze — full pipeline substep progression
5. WorkflowEngine._execute_analysis — integration with analysis phase
6. GET /api/workflows/{id}/research — research endpoint
7. OSM category mapping — _CATEGORY_TO_OSM correctness
8. Discovery category filtering — scan_zipcode with category
9. Evaluation phase — qualityPassed logic
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from backend.types import (
    BusinessPhase,
    BusinessWorkflowState,
    EvaluationResult,
    WorkflowDocument,
    WorkflowPhase,
    WorkflowProgress,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_business(
    slug: str,
    name: str = "",
    phase: BusinessPhase = BusinessPhase.PENDING,
    source_zip: str = "07003",
    business_type: str = "Barbershops",
    caps_completed: list[str] | None = None,
    caps_failed: list[str] | None = None,
    quality_passed: bool = False,
    evaluations: dict | None = None,
    official_url: str | None = None,
) -> BusinessWorkflowState:
    return BusinessWorkflowState(
        slug=slug,
        name=name or slug.replace("-", " ").title(),
        address="123 Main St",
        officialUrl=official_url,
        sourceZipCode=source_zip,
        businessType=business_type,
        phase=phase,
        capabilitiesCompleted=caps_completed or [],
        capabilitiesFailed=caps_failed or [],
        evaluations=evaluations or {},
        qualityPassed=quality_passed,
    )


def _make_workflow(
    workflow_id: str = "test-wf-001",
    phase: WorkflowPhase = WorkflowPhase.DISCOVERY,
    zip_code: str = "07003",
    business_type: str = "Barbershops",
    businesses: list[BusinessWorkflowState] | None = None,
) -> WorkflowDocument:
    return WorkflowDocument(
        id=workflow_id,
        zipCode=zip_code,
        businessType=business_type,
        phase=phase,
        createdAt=datetime.utcnow(),
        updatedAt=datetime.utcnow(),
        businesses=businesses or [],
        progress=WorkflowProgress(),
    )


# ===========================================================================
# 1. enqueue_agent_task
# ===========================================================================

class TestEnqueueAgentTask:
    """Tests for apps/api/backend/lib/tasks.py::enqueue_agent_task."""

    @patch("backend.lib.tasks.tasks_v2.CloudTasksClient")
    @patch("backend.lib.tasks.settings")
    def test_enqueue_success(self, mock_settings, mock_client_cls):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = "https://api.example.com"
        mock_client = MagicMock()
        mock_client.queue_path.return_value = "projects/test/locations/us-central1/queues/hephae-agent-queue"
        mock_response = MagicMock()
        mock_response.name = "projects/test/locations/us-central1/queues/hephae-agent-queue/tasks/abc123"
        mock_client.create_task.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = enqueue_agent_task("test-biz", "WORKFLOW_ANALYZE", "task-001")

        assert result == mock_response.name
        mock_client.create_task.assert_called_once()
        create_args = mock_client.create_task.call_args
        task = create_args.kwargs["request"]["task"]
        assert task["http_request"]["url"] == "https://api.example.com/api/research/tasks/execute"
        body = json.loads(task["http_request"]["body"])
        assert body["businessId"] == "test-biz"
        assert body["actionType"] == "WORKFLOW_ANALYZE"
        assert body["taskId"] == "task-001"

    @patch("backend.lib.tasks.tasks_v2.CloudTasksClient")
    @patch("backend.lib.tasks.settings")
    def test_enqueue_includes_metadata(self, mock_settings, mock_client_cls):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = "https://api.example.com"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "task-name"
        mock_client.create_task.return_value = mock_response
        mock_client.queue_path.return_value = "queue-path"
        mock_client_cls.return_value = mock_client

        metadata = {"workflowId": "wf-1", "sourceZipCode": "07003"}
        enqueue_agent_task("biz-1", "WORKFLOW_ANALYZE", "t-1", metadata=metadata)

        body = json.loads(mock_client.create_task.call_args.kwargs["request"]["task"]["http_request"]["body"])
        assert body["metadata"] == metadata

    @patch("backend.lib.tasks.tasks_v2.CloudTasksClient")
    @patch("backend.lib.tasks.settings")
    def test_enqueue_sets_dispatch_deadline(self, mock_settings, mock_client_cls):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = "https://api.example.com"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "task-name"
        mock_client.create_task.return_value = mock_response
        mock_client.queue_path.return_value = "queue-path"
        mock_client_cls.return_value = mock_client

        enqueue_agent_task("biz-1", "X", "t-1", dispatch_deadline_seconds=1800)

        task = mock_client.create_task.call_args.kwargs["request"]["task"]
        assert task["dispatch_deadline"]["seconds"] == 1800

    @patch("backend.lib.tasks.tasks_v2.CloudTasksClient")
    @patch("backend.lib.tasks.settings")
    def test_enqueue_includes_oidc_token(self, mock_settings, mock_client_cls):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = "https://api.example.com"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.name = "task-name"
        mock_client.create_task.return_value = mock_response
        mock_client.queue_path.return_value = "queue-path"
        mock_client_cls.return_value = mock_client

        enqueue_agent_task("biz-1", "X", "t-1")

        task = mock_client.create_task.call_args.kwargs["request"]["task"]
        assert "oidc_token" in task["http_request"]
        assert "service_account_email" in task["http_request"]["oidc_token"]

    @patch("backend.lib.tasks.settings")
    def test_enqueue_returns_none_without_base_url(self, mock_settings):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = ""
        with patch.dict("os.environ", {}, clear=True):
            result = enqueue_agent_task("biz-1", "X", "t-1")
        assert result is None

    @patch("backend.lib.tasks.tasks_v2.CloudTasksClient")
    @patch("backend.lib.tasks.settings")
    def test_enqueue_returns_none_on_api_error(self, mock_settings, mock_client_cls):
        from backend.lib.tasks import enqueue_agent_task

        mock_settings.API_BASE_URL = "https://api.example.com"
        mock_client = MagicMock()
        mock_client.queue_path.return_value = "queue-path"
        mock_client.create_task.side_effect = Exception("403 IAM permission denied")
        mock_client_cls.return_value = mock_client

        result = enqueue_agent_task("biz-1", "X", "t-1")
        assert result is None


# ===========================================================================
# 2. get_tasks_by_ids
# ===========================================================================

class TestGetTasksByIds:
    """Tests for packages/db/hephae_db/firestore/tasks.py::get_tasks_by_ids."""

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.tasks.get_db")
    async def test_returns_empty_for_empty_input(self, mock_get_db):
        from hephae_db.firestore.tasks import get_tasks_by_ids

        result = await get_tasks_by_ids([])
        assert result == []
        mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.tasks.get_db")
    async def test_fetches_multiple_tasks(self, mock_get_db):
        from hephae_db.firestore.tasks import get_tasks_by_ids

        doc1 = MagicMock()
        doc1.exists = True
        doc1.id = "t-1"
        doc1.to_dict.return_value = {"status": "completed", "metadata": {}}

        doc2 = MagicMock()
        doc2.exists = True
        doc2.id = "t-2"
        doc2.to_dict.return_value = {"status": "running", "metadata": {"substep": "enrichment_done"}}

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.side_effect = [doc1, doc2]
        mock_get_db.return_value = mock_db

        result = await get_tasks_by_ids(["t-1", "t-2"])
        assert len(result) == 2
        assert result[0]["id"] == "t-1"
        assert result[1]["id"] == "t-2"
        assert result[1]["metadata"]["substep"] == "enrichment_done"

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.tasks.get_db")
    async def test_skips_nonexistent_tasks(self, mock_get_db):
        from hephae_db.firestore.tasks import get_tasks_by_ids

        doc1 = MagicMock()
        doc1.exists = True
        doc1.id = "t-1"
        doc1.to_dict.return_value = {"status": "completed"}

        doc2 = MagicMock()
        doc2.exists = False

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.side_effect = [doc1, doc2]
        mock_get_db.return_value = mock_db

        result = await get_tasks_by_ids(["t-1", "t-missing"])
        assert len(result) == 1
        assert result[0]["id"] == "t-1"


# ===========================================================================
# 3. run_analysis_phase — enqueue + poll + callbacks
# ===========================================================================

class TestRunAnalysisPhase:
    """Tests for apps/api/backend/workflows/phases/analysis.py::run_analysis_phase."""

    @pytest.mark.asyncio
    async def test_skips_when_no_pending_businesses(self):
        from backend.workflows.phases.analysis import run_analysis_phase

        businesses = [_make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE)]
        callbacks = {"onBusinessDone": AsyncMock()}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")
        callbacks["onBusinessDone"].assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis._sleep", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_enqueues_one_task_per_business(
        self, mock_update_task, mock_create_task, mock_enqueue, mock_get_tasks, mock_sleep
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create_task.side_effect = ["task-1", "task-2"]
        mock_enqueue.side_effect = ["cloud-task-1", "cloud-task-2"]

        # Return completed tasks immediately
        mock_get_tasks.return_value = [
            {"id": "task-1", "status": "completed", "metadata": {"substep": "insights_done"}},
            {"id": "task-2", "status": "completed", "metadata": {"substep": "insights_done"}},
        ]

        businesses = [
            _make_business("biz-1", phase=BusinessPhase.PENDING),
            _make_business("biz-2", phase=BusinessPhase.PENDING),
        ]
        callbacks = {"onBusinessDone": AsyncMock()}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        assert mock_create_task.call_count == 2
        assert mock_enqueue.call_count == 2

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_marks_business_done_on_enqueue_failure(
        self, mock_update_task, mock_create_task, mock_enqueue, mock_get_tasks
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create_task.return_value = "task-1"
        mock_enqueue.return_value = None  # Enqueue fails

        businesses = [_make_business("biz-1", phase=BusinessPhase.PENDING)]
        on_done = AsyncMock()
        callbacks = {"onBusinessDone": on_done}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        assert businesses[0].phase == BusinessPhase.ANALYSIS_DONE
        on_done.assert_called_once_with("biz-1")
        mock_update_task.assert_called()

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis._sleep", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_fires_enrichment_callback_on_substep(
        self, mock_update, mock_create, mock_enqueue, mock_get_tasks, mock_sleep
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create.return_value = "task-1"
        mock_enqueue.return_value = "cloud-task-1"

        # First poll: enrichment_done, second poll: completed
        mock_get_tasks.side_effect = [
            [{"id": "task-1", "status": "running", "metadata": {"substep": "enrichment_done"}}],
            [{"id": "task-1", "status": "completed", "metadata": {"substep": "insights_done"}}],
        ]

        on_enrichment = MagicMock()
        on_done = AsyncMock()
        businesses = [_make_business("biz-1", phase=BusinessPhase.PENDING)]
        callbacks = {"onEnrichmentDone": on_enrichment, "onBusinessDone": on_done}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        on_enrichment.assert_called_once_with("biz-1", True)
        on_done.assert_called_once_with("biz-1")

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis._sleep", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_fires_capability_callback_on_substep(
        self, mock_update, mock_create, mock_enqueue, mock_get_tasks, mock_sleep
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create.return_value = "task-1"
        mock_enqueue.return_value = "cloud-task-1"

        mock_get_tasks.side_effect = [
            [{"id": "task-1", "status": "running", "metadata": {
                "substep": "capability_done:seo", "capabilitiesCompleted": ["seo"],
            }}],
            [{"id": "task-1", "status": "completed", "metadata": {"substep": "insights_done"}}],
        ]

        on_cap = MagicMock()
        on_done = AsyncMock()
        businesses = [_make_business("biz-1", phase=BusinessPhase.PENDING)]
        callbacks = {"onCapabilityDone": on_cap, "onBusinessDone": on_done}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        on_cap.assert_called_once_with("biz-1", "seo", True)

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis._sleep", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_handles_task_failure(
        self, mock_update, mock_create, mock_enqueue, mock_get_tasks, mock_sleep,
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create.return_value = "task-1"
        mock_enqueue.return_value = "cloud-task-1"

        mock_get_tasks.return_value = [
            {"id": "task-1", "status": "failed", "error": "Timeout", "metadata": {}},
        ]

        on_done = AsyncMock()
        businesses = [_make_business("biz-1", phase=BusinessPhase.PENDING)]
        callbacks = {"onBusinessDone": on_done}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        assert businesses[0].phase == BusinessPhase.ANALYSIS_DONE
        assert businesses[0].lastError == "Timeout"
        on_done.assert_called_once_with("biz-1")

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.analysis.get_tasks_by_ids", new_callable=AsyncMock)
    @patch("backend.lib.tasks.enqueue_agent_task")
    @patch("backend.workflows.phases.analysis.create_task", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis.update_task", new_callable=AsyncMock)
    async def test_returns_immediately_when_all_enqueues_fail(
        self, mock_update, mock_create, mock_enqueue, mock_get_tasks
    ):
        from backend.workflows.phases.analysis import run_analysis_phase

        mock_create.side_effect = ["t-1", "t-2"]
        mock_enqueue.return_value = None  # All fail

        businesses = [
            _make_business("biz-1", phase=BusinessPhase.PENDING),
            _make_business("biz-2", phase=BusinessPhase.PENDING),
        ]
        on_done = AsyncMock()
        callbacks = {"onBusinessDone": on_done}

        await run_analysis_phase(businesses, callbacks, workflow_id="wf-1")

        # Should not enter poll loop
        mock_get_tasks.assert_not_called()
        assert on_done.call_count == 2


# ===========================================================================
# 4. _run_workflow_analyze — substep progression
# ===========================================================================

class TestRunWorkflowAnalyze:
    """Tests for apps/api/backend/routers/admin/tasks.py::_run_workflow_analyze."""

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.insights.insights_agent.generate_insights", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis._run_capability", new_callable=AsyncMock)
    @patch("backend.workflows.capabilities.registry.get_enabled_capabilities")
    @patch("backend.workflows.phases.enrichment.enrich_business_profile", new_callable=AsyncMock)
    @patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock)
    @patch("hephae_common.firebase.get_db")
    @patch("hephae_db.firestore.tasks.update_task", new_callable=AsyncMock)
    async def test_full_pipeline_substep_progression(
        self, mock_update_task, mock_get_db, mock_get_biz, mock_enrich,
        mock_get_caps, mock_run_cap, mock_insights,
    ):
        from backend.routers.admin.tasks import _run_workflow_analyze

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.update = MagicMock()
        mock_get_db.return_value = mock_db

        mock_get_biz.side_effect = [
            {"name": "Test Biz", "address": "123 St", "identity": {"name": "Test Biz", "docId": "test-biz"}},
            {"name": "Test Biz", "address": "123 St", "identity": {"name": "Test Biz", "docId": "test-biz"}, "officialUrl": "https://test.com"},
        ]
        mock_enrich.return_value = {"name": "Test Biz", "phone": "555-1234"}

        cap = MagicMock()
        cap.name = "social"
        cap.firestore_output_key = "social_media_auditor"
        cap.should_run = None
        cap.response_adapter = lambda x: x
        cap.runner = AsyncMock(return_value={"report": "data"})
        mock_get_caps.return_value = [cap]
        mock_run_cap.return_value = {"report": "data"}
        mock_insights.return_value = {"summary": "test"}

        result = await _run_workflow_analyze("test-biz", "task-1", {
            "sourceZipCode": "", "businessType": "Barbershops",
        })

        assert "social" in result["capabilitiesCompleted"]
        assert result["insights"] is True

        # Verify substep updates
        substep_calls = [
            c for c in mock_update_task.call_args_list
            if "metadata.substep" in (c.args[1] if len(c.args) > 1 else c.kwargs.get("updates", {}))
        ]
        substeps = [
            (c.args[1] if len(c.args) > 1 else c.kwargs.get("updates", {}))["metadata.substep"]
            for c in substep_calls
        ]
        assert "enrichment_done" in substeps
        assert "insights_done" in substeps
        assert any(s.startswith("capability_done:") for s in substeps)

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock)
    @patch("hephae_db.firestore.tasks.update_task", new_callable=AsyncMock)
    async def test_business_not_found_raises(self, mock_update, mock_get_biz):
        from backend.routers.admin.tasks import _run_workflow_analyze

        mock_get_biz.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await _run_workflow_analyze("missing-biz", "task-1", {})

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.insights.insights_agent.generate_insights", new_callable=AsyncMock)
    @patch("backend.workflows.phases.analysis._run_capability", new_callable=AsyncMock)
    @patch("backend.workflows.capabilities.registry.get_enabled_capabilities")
    @patch("backend.workflows.phases.enrichment.enrich_business_profile", new_callable=AsyncMock)
    @patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock)
    @patch("hephae_common.firebase.get_db")
    @patch("hephae_db.firestore.tasks.update_task", new_callable=AsyncMock)
    async def test_skips_capabilities_without_official_url(
        self, mock_update, mock_get_db, mock_get_biz, mock_enrich,
        mock_get_caps, mock_run_cap, mock_insights,
    ):
        from backend.routers.admin.tasks import _run_workflow_analyze

        mock_get_db.return_value = MagicMock()
        mock_get_biz.side_effect = [
            {"name": "No Website Biz", "address": "123 St"},
            {"name": "No Website Biz", "address": "123 St", "identity": {"name": "No Website Biz", "docId": "no-web"}},
        ]
        mock_enrich.return_value = None

        seo_cap = MagicMock()
        seo_cap.name = "seo"
        seo_cap.should_run = lambda biz: bool(biz.get("officialUrl"))
        social_cap = MagicMock()
        social_cap.name = "social"
        social_cap.should_run = None
        social_cap.firestore_output_key = "social_media_auditor"
        social_cap.response_adapter = lambda x: x
        mock_get_caps.return_value = [seo_cap, social_cap]
        mock_run_cap.return_value = {"report": "data"}
        mock_insights.return_value = None

        result = await _run_workflow_analyze("no-web", "task-1", {})

        # SEO should be skipped, social should run
        assert "social" in result["capabilitiesCompleted"]
        assert "seo" not in result["capabilitiesCompleted"]


# ===========================================================================
# 5. WorkflowEngine
# ===========================================================================

class TestWorkflowEngine:
    """Tests for apps/api/backend/workflows/engine.py::WorkflowEngine."""

    @pytest.mark.asyncio
    @patch("backend.workflows.engine.save_workflow", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_outreach_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_evaluation_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_analysis_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_discovery_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.research_zip_code", new_callable=AsyncMock)
    async def test_passes_workflow_id_to_analysis_phase(
        self, mock_research, mock_discovery, mock_analysis,
        mock_eval, mock_outreach, mock_save,
    ):
        from backend.workflows.engine import WorkflowEngine

        businesses = [_make_business("biz-1", phase=BusinessPhase.PENDING)]
        workflow = _make_workflow(
            workflow_id="wf-test-123",
            phase=WorkflowPhase.ANALYSIS,
            businesses=businesses,
        )

        # Make evaluation phase transition to approval so engine pauses
        async def _fake_eval(biz_list, callbacks):
            for b in biz_list:
                b.phase = BusinessPhase.EVALUATION_DONE
        mock_eval.side_effect = _fake_eval

        engine = WorkflowEngine(workflow)
        await engine.run()

        mock_analysis.assert_called_once()
        call_kwargs = mock_analysis.call_args
        assert call_kwargs.kwargs.get("workflow_id") == "wf-test-123" or \
               (len(call_kwargs.args) >= 3 and call_kwargs.args[2] == "wf-test-123")

    @pytest.mark.asyncio
    @patch("backend.workflows.engine.save_workflow", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_analysis_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_discovery_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.research_zip_code", new_callable=AsyncMock)
    async def test_engine_emits_progress_events(
        self, mock_research, mock_discovery, mock_analysis, mock_save,
    ):
        from backend.workflows.engine import WorkflowEngine

        mock_discovery.return_value = [
            {"slug": "biz-1", "name": "Biz One", "address": "123 St"},
        ]

        workflow = _make_workflow(phase=WorkflowPhase.DISCOVERY)

        events = []
        engine = WorkflowEngine(workflow, on_progress=lambda e: events.append(e))

        # Engine will fail at analysis since we don't mock eval/outreach
        # but we can check discovery events
        mock_analysis.side_effect = Exception("stop here")

        await engine.run()

        event_types = [e.type for e in events]
        assert "workflow:started" in event_types
        assert "workflow:phase_changed" in event_types

    @pytest.mark.asyncio
    @patch("backend.workflows.engine.save_workflow", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_discovery_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.research_zip_code", new_callable=AsyncMock)
    async def test_engine_sets_failed_on_error(
        self, mock_research, mock_discovery, mock_save,
    ):
        from backend.workflows.engine import WorkflowEngine

        mock_discovery.side_effect = ValueError("No businesses discovered")

        workflow = _make_workflow(phase=WorkflowPhase.DISCOVERY)
        engine = WorkflowEngine(workflow)
        await engine.run()

        assert workflow.phase == WorkflowPhase.FAILED
        assert "No businesses discovered" in (workflow.lastError or "")

    @pytest.mark.asyncio
    @patch("backend.workflows.engine.save_workflow", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_evaluation_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_analysis_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.run_discovery_phase", new_callable=AsyncMock)
    @patch("backend.workflows.engine.research_zip_code", new_callable=AsyncMock)
    async def test_engine_pauses_at_approval(
        self, mock_research, mock_discovery, mock_analysis, mock_eval, mock_save,
    ):
        from backend.workflows.engine import WorkflowEngine

        mock_discovery.return_value = [
            {"slug": "biz-1", "name": "Biz One", "address": "123 St"},
        ]
        async def _fake_eval(biz_list, callbacks):
            for b in biz_list:
                b.phase = BusinessPhase.EVALUATION_DONE
        mock_eval.side_effect = _fake_eval

        workflow = _make_workflow(phase=WorkflowPhase.DISCOVERY)
        engine = WorkflowEngine(workflow)
        await engine.run()

        assert workflow.phase == WorkflowPhase.APPROVAL


# ===========================================================================
# 6. GET /api/workflows/{id}/research
# ===========================================================================

class TestWorkflowResearchEndpoint:
    """Tests for the /api/workflows/{id}/research endpoint."""

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.research.get_area_research_for_zip_code", new_callable=AsyncMock)
    @patch("hephae_db.firestore.research.get_zipcode_report", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_returns_research_for_single_zipcode(
        self, mock_load, mock_zip_report, mock_area, client,
    ):
        workflow = _make_workflow(zip_code="07003")
        mock_load.return_value = workflow

        report_mock = MagicMock()
        report_mock.report = MagicMock()
        report_mock.report.model_dump.return_value = {"summary": "Test report", "sections": {}}
        mock_zip_report.return_value = report_mock
        mock_area.return_value = None

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.get("/api/workflows/test-wf-001/research")
            assert resp.status_code == 200
            data = resp.json()
            assert "zipReports" in data
            assert "areaResearch" in data
            assert "07003" in data["zipReports"]
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)

    @pytest.mark.asyncio
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_returns_404_for_missing_workflow(self, mock_load, client):
        mock_load.return_value = None

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.get("/api/workflows/nonexistent/research")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)

    @pytest.mark.asyncio
    @patch("hephae_db.firestore.research.get_area_research_for_zip_code", new_callable=AsyncMock)
    @patch("hephae_db.firestore.research.get_zipcode_report", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_returns_empty_when_no_research_exists(
        self, mock_load, mock_zip_report, mock_area, client,
    ):
        workflow = _make_workflow(zip_code="99999")
        mock_load.return_value = workflow
        mock_zip_report.return_value = None
        mock_area.return_value = None

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.get("/api/workflows/test-wf-001/research")
            assert resp.status_code == 200
            data = resp.json()
            assert data["zipReports"] == {}
            assert data["areaResearch"] == {}
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)


# ===========================================================================
# 7. OSM category mapping
# ===========================================================================

class TestOsmCategoryMapping:
    """Tests for packages/integrations/hephae_integrations/osm_client.py."""

    def test_all_business_types_have_osm_mapping(self):
        from hephae_integrations.osm_client import _CATEGORY_TO_OSM

        business_types = [
            "Restaurants", "Bakeries", "Barbershops", "Hair Salons",
            "Nail Salons", "Coffee Shops", "Dentists", "Auto Repair",
            "Gyms", "Florists", "Pet Groomers", "Dry Cleaners",
            "Pizza Shops", "Delis", "Spas",
        ]

        for bt in business_types:
            key = bt.lower().strip()
            assert key in _CATEGORY_TO_OSM, f"Missing OSM mapping for '{bt}'"

    def test_singular_forms_mapped(self):
        from hephae_integrations.osm_client import _CATEGORY_TO_OSM

        singular_forms = [
            "restaurant", "bakery", "cafe", "bar", "dentist",
            "gym", "salon", "florist", "spa", "deli",
        ]

        for form in singular_forms:
            assert form in _CATEGORY_TO_OSM, f"Missing singular mapping for '{form}'"

    def test_mapping_values_are_valid_osm_tags(self):
        from hephae_integrations.osm_client import _CATEGORY_TO_OSM

        valid_keys = {"amenity", "shop", "craft", "office"}
        for category, (osm_key, osm_val) in _CATEGORY_TO_OSM.items():
            assert osm_key in valid_keys, f"Invalid OSM key '{osm_key}' for '{category}'"
            assert osm_val, f"Empty OSM value for '{category}'"

    def test_overpass_query_uses_mapping(self):
        from hephae_integrations.osm_client import _build_overpass_query

        query = _build_overpass_query(40.8, -74.2, category="Bakeries")
        assert '"amenity"="bakery"' in query

    def test_overpass_query_fallback_for_unknown_category(self):
        from hephae_integrations.osm_client import _build_overpass_query

        query = _build_overpass_query(40.8, -74.2, category="Underwater Basket Weaving")
        # Should use fuzzy name match fallback
        assert '"name"~' in query

    def test_overpass_query_without_category_is_broad(self):
        from hephae_integrations.osm_client import _build_overpass_query

        query = _build_overpass_query(40.8, -74.2, category=None)
        # Should search for multiple amenity types
        assert "restaurant" in query
        assert "shop" in query


# ===========================================================================
# 8. Discovery category filtering
# ===========================================================================

class TestDiscoveryCategoryFiltering:
    """Tests for scan_zipcode with category parameter."""

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_hub_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_adk_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.osm_discover", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.get_businesses_in_zipcode", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.save_business", new_callable=AsyncMock)
    async def test_category_passed_to_all_sources(
        self, mock_save, mock_cache, mock_osm, mock_adk, mock_hub,
    ):
        from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode

        mock_osm.return_value = []
        mock_adk.return_value = []
        mock_hub.return_value = []

        await scan_zipcode("07003", category="Bakeries", force=True)

        mock_osm.assert_called_once()
        assert mock_osm.call_args.kwargs.get("category") == "Bakeries" or \
               (len(mock_osm.call_args.args) > 1 and mock_osm.call_args.args[1] == "Bakeries")

        mock_adk.assert_called_once()
        assert mock_adk.call_args.kwargs.get("category") == "Bakeries"

        mock_hub.assert_called_once()
        assert mock_hub.call_args.kwargs.get("category") == "Bakeries"

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_hub_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_adk_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.osm_discover", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.get_businesses_in_zipcode", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.save_business", new_callable=AsyncMock)
    async def test_category_bypasses_cache(
        self, mock_save, mock_cache, mock_osm, mock_adk, mock_hub,
    ):
        from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode

        mock_osm.return_value = []
        mock_adk.return_value = []
        mock_hub.return_value = []

        await scan_zipcode("07003", category="Bakeries")

        # With category set, cache should be bypassed
        mock_cache.assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_hub_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_adk_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.osm_discover", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.get_businesses_in_zipcode", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.save_business", new_callable=AsyncMock)
    async def test_dedup_prefers_hub_over_adk(
        self, mock_save, mock_cache, mock_osm, mock_adk, mock_hub,
    ):
        from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode

        mock_osm.return_value = []
        mock_hub.return_value = [
            {"name": "Best Bakery", "address": "123 Main St", "website": "https://hub.com", "category": "bakery"},
        ]
        mock_adk.return_value = [
            {"name": "Best Bakery", "address": "456 Oak Ave", "website": "https://adk.com", "category": "bakery"},
        ]

        results = await scan_zipcode("07003", category="Bakeries", force=True)

        assert len(results) == 1
        assert results[0].website == "https://hub.com"  # Hub takes priority

    @pytest.mark.asyncio
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_hub_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner._run_adk_discovery", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.osm_discover", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.get_businesses_in_zipcode", new_callable=AsyncMock)
    @patch("backend.workflows.agents.discovery.zipcode_scanner.save_business", new_callable=AsyncMock)
    async def test_handles_source_failure_gracefully(
        self, mock_save, mock_cache, mock_osm, mock_adk, mock_hub,
    ):
        from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode
        from hephae_integrations.osm_client import OsmBusiness

        mock_osm.return_value = [
            OsmBusiness(name="OSM Bakery", category="bakery", address="789 St", phone="", website=""),
        ]
        mock_adk.side_effect = Exception("ADK agent crashed")
        mock_hub.side_effect = Exception("Hub crawl failed")

        results = await scan_zipcode("07003", category="Bakeries", force=True)

        assert len(results) == 1
        assert results[0].name == "OSM Bakery"

    def test_discovery_phase_passes_category(self):
        """Verify run_discovery_phase calls scan_zipcode with category."""
        import inspect
        from backend.workflows.phases.discovery import run_discovery_phase

        source = inspect.getsource(run_discovery_phase)
        assert "category=business_type" in source


# ===========================================================================
# 9. Evaluation phase — qualityPassed logic
# ===========================================================================

class TestEvaluationPhase:
    """Tests for apps/api/backend/workflows/phases/evaluation.py."""

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.run_agent_to_json", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_quality_passes_when_all_scores_high(
        self, mock_get_caps, mock_get_biz, mock_run_agent,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        cap = MagicMock()
        cap.name = "seo"
        cap.firestore_output_key = "seo_auditor"
        cap.evaluator = MagicMock()
        cap.evaluator.agent_factory.return_value = MagicMock()
        cap.evaluator.build_prompt.return_value = "evaluate this"
        cap.evaluator.app_name = "test"
        mock_get_caps.return_value = [cap]

        mock_get_biz.return_value = {
            "identity": {"name": "Test", "officialUrl": "https://test.com"},
            "latestOutputs": {"seo_auditor": {"report": "data"}},
        }
        mock_run_agent.return_value = {"score": 90, "isHallucinated": False, "issues": []}

        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE, caps_completed=["seo"])
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        assert biz.qualityPassed is True
        assert biz.phase == BusinessPhase.EVALUATION_DONE
        on_eval.assert_called_once_with("biz-1", True)

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.run_agent_to_json", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_quality_fails_when_score_below_80(
        self, mock_get_caps, mock_get_biz, mock_run_agent,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        cap = MagicMock()
        cap.name = "seo"
        cap.firestore_output_key = "seo_auditor"
        cap.evaluator = MagicMock()
        cap.evaluator.agent_factory.return_value = MagicMock()
        cap.evaluator.build_prompt.return_value = "evaluate"
        cap.evaluator.app_name = "test"
        mock_get_caps.return_value = [cap]

        mock_get_biz.return_value = {
            "identity": {"name": "Test"},
            "latestOutputs": {"seo_auditor": {"report": "bad"}},
        }
        mock_run_agent.return_value = {"score": 50, "isHallucinated": False, "issues": ["low quality"]}

        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE, caps_completed=["seo"])
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        assert biz.qualityPassed is False
        on_eval.assert_called_once_with("biz-1", False)

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.run_agent_to_json", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_quality_fails_when_hallucinated(
        self, mock_get_caps, mock_get_biz, mock_run_agent,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        cap = MagicMock()
        cap.name = "seo"
        cap.firestore_output_key = "seo_auditor"
        cap.evaluator = MagicMock()
        cap.evaluator.agent_factory.return_value = MagicMock()
        cap.evaluator.build_prompt.return_value = "evaluate"
        cap.evaluator.app_name = "test"
        mock_get_caps.return_value = [cap]

        mock_get_biz.return_value = {
            "identity": {"name": "Test"},
            "latestOutputs": {"seo_auditor": {"report": "data"}},
        }
        mock_run_agent.return_value = {"score": 95, "isHallucinated": True, "issues": ["hallucination"]}

        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE, caps_completed=["seo"])
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        assert biz.qualityPassed is False

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.run_agent_to_json", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_quality_fails_with_no_evaluations(
        self, mock_get_caps, mock_get_biz, mock_run_agent,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        mock_get_caps.return_value = []  # No evaluable capabilities
        mock_get_biz.return_value = {"identity": {"name": "Test"}, "latestOutputs": {}}

        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE)
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        assert biz.qualityPassed is False
        assert biz.phase == BusinessPhase.EVALUATION_DONE

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_evaluation_handles_error_gracefully(
        self, mock_get_caps, mock_get_biz,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        mock_get_biz.side_effect = Exception("Firestore unavailable")
        mock_get_caps.return_value = [MagicMock()]

        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE)
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        assert biz.phase == BusinessPhase.EVALUATION_DONE
        assert biz.qualityPassed is False
        assert biz.lastError is not None

    @pytest.mark.asyncio
    @patch("backend.workflows.phases.evaluation.run_agent_to_json", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_business", new_callable=AsyncMock)
    @patch("backend.workflows.phases.evaluation.get_evaluable_capabilities")
    async def test_skips_caps_not_in_completed_list(
        self, mock_get_caps, mock_get_biz, mock_run_agent,
    ):
        from backend.workflows.phases.evaluation import run_evaluation_phase

        cap = MagicMock()
        cap.name = "seo"
        cap.firestore_output_key = "seo_auditor"
        cap.evaluator = MagicMock()
        mock_get_caps.return_value = [cap]

        mock_get_biz.return_value = {
            "identity": {"name": "Test"},
            "latestOutputs": {"seo_auditor": {"report": "data"}},
        }

        # Business only completed 'social', not 'seo'
        biz = _make_business("biz-1", phase=BusinessPhase.ANALYSIS_DONE, caps_completed=["social"])
        on_eval = AsyncMock()

        await run_evaluation_phase([biz], {"onBusinessEvaluated": on_eval})

        mock_run_agent.assert_not_called()
        assert biz.qualityPassed is False


# ===========================================================================
# 10. Workflow action endpoints
# ===========================================================================

class TestWorkflowActionEndpoints:
    """Tests for apps/api/backend/routers/admin/workflow_actions.py."""

    @pytest.mark.asyncio
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_get_workflow_returns_data(self, mock_load, client):
        workflow = _make_workflow()
        mock_load.return_value = workflow

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.get("/api/workflows/test-wf-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["zipCode"] == "07003"
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)

    @pytest.mark.asyncio
    @patch("backend.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_force_stop_marks_failed(self, mock_load, mock_save, client):
        workflow = _make_workflow(phase=WorkflowPhase.ANALYSIS)
        mock_load.return_value = workflow

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.patch("/api/workflows/test-wf-001")
            assert resp.status_code == 200
            assert workflow.phase == WorkflowPhase.FAILED
            mock_save.assert_called_once()
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)

    @pytest.mark.asyncio
    @patch("backend.routers.admin.workflow_actions.start_workflow_engine", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_resume_only_works_on_failed(self, mock_load, mock_save, mock_start, client):
        workflow = _make_workflow(phase=WorkflowPhase.ANALYSIS)
        mock_load.return_value = workflow

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.post("/api/workflows/test-wf-001/resume")
            assert resp.status_code == 400
            assert "failed" in resp.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)

    @pytest.mark.asyncio
    @patch("backend.routers.admin.workflow_actions.WorkflowEngine")
    @patch("backend.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock)
    @patch("backend.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock)
    async def test_approve_rejects_non_approval_phase(self, mock_load, mock_save, mock_engine, client):
        workflow = _make_workflow(phase=WorkflowPhase.ANALYSIS)
        mock_load.return_value = workflow

        from backend.lib.auth import verify_admin_request
        from backend.main import app
        app.dependency_overrides[verify_admin_request] = lambda: None

        try:
            resp = await client.post(
                "/api/workflows/test-wf-001/approve",
                json={"approvals": {"biz-1": "approve"}},
            )
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(verify_admin_request, None)
