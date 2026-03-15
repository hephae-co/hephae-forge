"""Unit tests for admin API endpoints — test runner, workflows, stats."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked Firebase and bypassed admin auth."""
    with patch("hephae_common.firebase.get_db"):
        from hephae_api.main import app
        from hephae_api.lib.auth import verify_admin_request

        # Override the admin auth dependency so tests don't need real Firebase tokens
        app.dependency_overrides[verify_admin_request] = lambda: {"uid": "test-admin", "email": "admin@test.com"}
        yield TestClient(app)
        app.dependency_overrides.pop(verify_admin_request, None)


# ---------------------------------------------------------------------------
# Test Runner endpoints
# ---------------------------------------------------------------------------

class TestRunTests:
    """POST /api/run-tests"""

    def test_run_tests_success(self, client):
        summary = {
            "runId": "run_123",
            "timestamp": "2026-03-10T12:00:00",
            "totalTests": 4,
            "passedTests": 3,
            "failedTests": 1,
            "results": [
                {"capability": "seo", "businessId": "qa-test-001", "businessName": "Test Biz", "score": 85, "isHallucinated": False, "issues": [], "responseTimeMs": 1200},
                {"capability": "traffic", "businessId": "qa-test-001", "businessName": "Test Biz", "score": 90, "isHallucinated": False, "issues": [], "responseTimeMs": 800},
                {"capability": "competitive", "businessId": "qa-test-001", "businessName": "Test Biz", "score": 82, "isHallucinated": False, "issues": [], "responseTimeMs": 1500},
                {"capability": "margin", "businessId": "qa-test-001", "businessName": "Test Biz", "score": 60, "isHallucinated": True, "issues": ["Low score"], "responseTimeMs": 2000},
            ],
        }
        with patch("hephae_api.workflows.test_runner.test_runner.run_all_tests", new_callable=AsyncMock, return_value=summary):
            response = client.post("/api/run-tests")
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == "run_123"
        assert data["totalTests"] == 4
        assert data["passedTests"] == 3
        assert len(data["results"]) == 4

    def test_run_tests_error(self, client):
        with patch("hephae_api.workflows.test_runner.test_runner.run_all_tests", new_callable=AsyncMock, side_effect=Exception("Agent timeout")):
            response = client.post("/api/run-tests")
        assert response.status_code == 500
        assert "Agent timeout" in response.json()["detail"]


class TestGetTestRuns:
    """GET /api/run-tests"""

    def test_get_runs_returns_history(self, client):
        runs = [
            {"runId": "run_2", "timestamp": "2026-03-10T14:00:00", "totalTests": 4, "passedTests": 4, "failedTests": 0, "results": []},
            {"runId": "run_1", "timestamp": "2026-03-10T12:00:00", "totalTests": 4, "passedTests": 3, "failedTests": 1, "results": []},
        ]
        with patch("hephae_db.firestore.test_runs.list_test_runs", new_callable=AsyncMock, return_value=runs):
            response = client.get("/api/run-tests")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["runId"] == "run_2"

    def test_get_runs_fallback_on_error(self, client):
        with patch("hephae_db.firestore.test_runs.list_test_runs", new_callable=AsyncMock, side_effect=Exception("DB down")):
            response = client.get("/api/run-tests")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_runs_with_limit(self, client):
        with patch("hephae_db.firestore.test_runs.list_test_runs", new_callable=AsyncMock, return_value=[]) as mock_list:
            response = client.get("/api/run-tests?limit=5")
        assert response.status_code == 200
        mock_list.assert_called_once_with(limit=5)


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

class TestStats:
    """GET /api/stats"""

    def test_get_stats(self, client):
        stats = {
            "totalBusinesses": 42,
            "totalWorkflows": 7,
            "totalReports": 150,
            "activeWorkflows": 2,
        }
        with patch("hephae_api.routers.admin.stats.get_dashboard_stats", new_callable=AsyncMock, return_value=stats):
            response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["totalBusinesses"] == 42


# ---------------------------------------------------------------------------
# Workflow CRUD endpoints
# ---------------------------------------------------------------------------

class TestWorkflows:
    """POST/GET /api/workflows"""

    def test_create_workflow_success(self, client):
        mock_wf = MagicMock()
        mock_wf.id = "wf-abc"
        with patch("hephae_api.routers.admin.workflows.create_workflow", new_callable=AsyncMock, return_value=mock_wf), \
             patch("hephae_api.routers.admin.workflows.start_workflow_engine", new_callable=AsyncMock):
            response = client.post("/api/workflows", json={"zipCode": "07110"})
        assert response.status_code == 200
        assert response.json()["workflowId"] == "wf-abc"
        assert response.json()["status"] == "started"

    def test_create_workflow_invalid_zip(self, client):
        response = client.post("/api/workflows", json={"zipCode": "abc"})
        assert response.status_code == 400
        assert "5 digits" in response.json()["detail"]

    def test_create_workflow_empty_zip(self, client):
        response = client.post("/api/workflows", json={"zipCode": ""})
        assert response.status_code == 400

    def test_list_workflows(self, client):
        mock_wf = MagicMock()
        mock_wf.model_dump.return_value = {"id": "wf-1", "phase": "completed", "businesses": []}
        with patch("hephae_api.routers.admin.workflows.list_workflows", new_callable=AsyncMock, return_value=[mock_wf]):
            response = client.get("/api/workflows")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_county_workflow_success(self, client):
        mock_wf = MagicMock()
        mock_wf.id = "wf-county"
        mock_resolved = MagicMock()
        mock_resolved.zipCodes = ["07110", "07111", "07112"]
        mock_resolved.countyName = "Essex"
        mock_resolved.state = "NJ"
        mock_resolved.error = None

        with patch("hephae_api.routers.admin.workflows.resolve_county_zip_codes", new_callable=AsyncMock, return_value=mock_resolved), \
             patch("hephae_api.routers.admin.workflows.create_workflow", new_callable=AsyncMock, return_value=mock_wf), \
             patch("hephae_api.routers.admin.workflows.start_workflow_engine", new_callable=AsyncMock):
            response = client.post("/api/workflows/county", json={
                "businessType": "restaurant",
                "county": "Essex County, NJ",
            })
        assert response.status_code == 200
        data = response.json()
        assert data["workflowId"] == "wf-county"
        assert len(data["zipCodes"]) == 3

    def test_create_county_workflow_no_zips(self, client):
        mock_resolved = MagicMock()
        mock_resolved.zipCodes = []
        mock_resolved.error = "Could not resolve county"
        with patch("hephae_api.routers.admin.workflows.resolve_county_zip_codes", new_callable=AsyncMock, return_value=mock_resolved):
            response = client.post("/api/workflows/county", json={
                "businessType": "restaurant",
                "county": "Fake County",
            })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Workflow Action endpoints
# ---------------------------------------------------------------------------

class TestWorkflowActions:
    """GET/PATCH/DELETE /api/workflows/{id}, approve, resume"""

    def _mock_workflow(self, **overrides):
        from hephae_api.types import WorkflowPhase
        wf = MagicMock()
        wf.phase = overrides.get("phase", WorkflowPhase.DISCOVERY)
        wf.businesses = overrides.get("businesses", [])
        wf.lastError = overrides.get("lastError", None)
        wf.retryCount = overrides.get("retryCount", 0)
        wf.model_dump.return_value = {"id": "wf-1", "phase": wf.phase.value, "businesses": []}
        return wf

    def test_get_workflow(self, client):
        wf = self._mock_workflow()
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf):
            response = client.get("/api/workflows/wf-1")
        assert response.status_code == 200

    def test_get_workflow_not_found(self, client):
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/workflows/nonexistent")
        assert response.status_code == 404

    def test_force_stop_workflow(self, client):
        from hephae_api.types import WorkflowPhase
        wf = self._mock_workflow(phase=WorkflowPhase.DISCOVERY)
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf), \
             patch("hephae_api.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock):
            response = client.patch("/api/workflows/wf-1")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert wf.phase == WorkflowPhase.FAILED

    def test_delete_workflow(self, client):
        with patch("hephae_api.routers.admin.workflow_actions.delete_workflow", new_callable=AsyncMock, return_value={"businessesRemoved": 5}):
            response = client.delete("/api/workflows/wf-1")
        assert response.status_code == 200
        assert response.json()["businessesRemoved"] == 5

    def test_delete_workflow_error(self, client):
        with patch("hephae_api.routers.admin.workflow_actions.delete_workflow", new_callable=AsyncMock, side_effect=ValueError("Cannot delete running")):
            response = client.delete("/api/workflows/wf-1")
        assert response.status_code == 400

    def test_approve_workflow(self, client):
        from hephae_api.types import WorkflowPhase, BusinessPhase
        biz = MagicMock()
        biz.slug = "test-biz"
        biz.phase = BusinessPhase.EVALUATION_DONE
        wf = self._mock_workflow(phase=WorkflowPhase.APPROVAL, businesses=[biz])
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf), \
             patch("hephae_api.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock), \
             patch("hephae_api.routers.admin.workflow_actions.WorkflowEngine"), \
             patch("hephae_api.routers.admin.workflow_actions.asyncio"):
            response = client.post("/api/workflows/wf-1/approve", json={"approvals": {"test-biz": "approve"}})
        assert response.status_code == 200
        assert response.json()["approved"] is True
        assert biz.phase == BusinessPhase.APPROVED

    def test_approve_wrong_phase(self, client):
        from hephae_api.types import WorkflowPhase
        wf = self._mock_workflow(phase=WorkflowPhase.DISCOVERY)
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf):
            response = client.post("/api/workflows/wf-1/approve", json={"approvals": {}})
        assert response.status_code == 400
        assert "not approval" in response.json()["detail"]

    def test_resume_failed_workflow(self, client):
        from hephae_api.types import WorkflowPhase
        wf = self._mock_workflow(phase=WorkflowPhase.FAILED)
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf), \
             patch("hephae_api.routers.admin.workflow_actions.save_workflow", new_callable=AsyncMock), \
             patch("hephae_api.routers.admin.workflow_actions.start_workflow_engine", new_callable=AsyncMock):
            response = client.post("/api/workflows/wf-1/resume")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_resume_non_failed_rejected(self, client):
        from hephae_api.types import WorkflowPhase
        wf = self._mock_workflow(phase=WorkflowPhase.DISCOVERY)
        with patch("hephae_api.routers.admin.workflow_actions.load_workflow", new_callable=AsyncMock, return_value=wf):
            response = client.post("/api/workflows/wf-1/resume")
        assert response.status_code == 400
        assert "failed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Fixtures endpoints
# ---------------------------------------------------------------------------

class TestFixtures:
    """POST/GET/DELETE /api/fixtures"""

    def test_create_fixture(self, client):
        mock_wf = MagicMock()
        mock_biz = MagicMock()
        mock_biz.slug = "test-biz"
        mock_biz.name = "Test Biz"
        mock_biz.address = "123 Main"
        mock_biz.sourceZipCode = "07110"
        mock_biz.businessType = "restaurant"
        mock_biz.model_dump.return_value = {"slug": "test-biz"}
        mock_wf.businesses = [mock_biz]

        with patch("hephae_api.routers.admin.fixtures.load_workflow", new_callable=AsyncMock, return_value=mock_wf), \
             patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value={"latestOutputs": {}}), \
             patch("hephae_api.routers.admin.fixtures.save_fixture", new_callable=AsyncMock, return_value="fix-123"):
            response = client.post("/api/fixtures", json={
                "workflowId": "wf-1",
                "businessSlug": "test-biz",
                "fixtureType": "grounding",
            })
        assert response.status_code == 200
        assert response.json()["fixtureId"] == "fix-123"

    def test_create_fixture_workflow_not_found(self, client):
        with patch("hephae_api.routers.admin.fixtures.load_workflow", new_callable=AsyncMock, return_value=None):
            response = client.post("/api/fixtures", json={
                "workflowId": "nonexistent",
                "businessSlug": "test-biz",
                "fixtureType": "grounding",
            })
        assert response.status_code == 404

    def test_create_fixture_business_not_found(self, client):
        mock_wf = MagicMock()
        mock_wf.businesses = []
        with patch("hephae_api.routers.admin.fixtures.load_workflow", new_callable=AsyncMock, return_value=mock_wf):
            response = client.post("/api/fixtures", json={
                "workflowId": "wf-1",
                "businessSlug": "nonexistent",
                "fixtureType": "grounding",
            })
        assert response.status_code == 404

    def test_list_fixtures(self, client):
        with patch("hephae_api.routers.admin.fixtures.list_fixtures", new_callable=AsyncMock, return_value=[{"id": "f1"}, {"id": "f2"}]):
            response = client.get("/api/fixtures")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_fixtures_with_type(self, client):
        with patch("hephae_api.routers.admin.fixtures.list_fixtures", new_callable=AsyncMock, return_value=[]) as mock_list:
            response = client.get("/api/fixtures?type=grounding")
        assert response.status_code == 200
        mock_list.assert_called_once_with(fixture_type="grounding")

    def test_get_fixture(self, client):
        with patch("hephae_api.routers.admin.fixtures.get_fixture", new_callable=AsyncMock, return_value={"id": "f1", "fixtureType": "grounding"}):
            response = client.get("/api/fixtures/f1")
        assert response.status_code == 200

    def test_get_fixture_not_found(self, client):
        with patch("hephae_api.routers.admin.fixtures.get_fixture", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/fixtures/nonexistent")
        assert response.status_code == 404

    def test_delete_fixture(self, client):
        with patch("hephae_api.routers.admin.fixtures.delete_fixture", new_callable=AsyncMock):
            response = client.delete("/api/fixtures/f1")
        assert response.status_code == 200
        assert response.json()["success"] is True


# ---------------------------------------------------------------------------
# Zipcode Research endpoints
# ---------------------------------------------------------------------------

class TestZipcodeResearch:
    """POST/GET/DELETE /api/zipcode-research"""

    def test_start_research(self, client):
        result = {"report": {"summary": "Test"}, "runId": "run-1"}
        with patch("hephae_api.routers.admin.zipcode_research.research_zip_code", new_callable=AsyncMock, return_value=result):
            response = client.post("/api/zipcode-research/07110")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["runId"] == "run-1"

    def test_start_research_invalid_zip(self, client):
        response = client.post("/api/zipcode-research/abc")
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    def test_get_report(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.get_zipcode_report", new_callable=AsyncMock, return_value={"zipCode": "07110", "summary": "data"}):
            response = client.get("/api/zipcode-research/07110")
        assert response.status_code == 200

    def test_get_report_not_found(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.get_zipcode_report", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/zipcode-research/99999")
        assert response.status_code == 404

    def test_list_runs(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.list_zipcode_runs", new_callable=AsyncMock, return_value=[{"id": "r1"}]):
            response = client.get("/api/zipcode-research")
        assert response.status_code == 200

    def test_get_run(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.get_run", new_callable=AsyncMock, return_value={"id": "r1"}):
            response = client.get("/api/zipcode-research/runs/r1")
        assert response.status_code == 200

    def test_get_run_not_found(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.get_run", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/zipcode-research/runs/nonexistent")
        assert response.status_code == 404

    def test_delete_run(self, client):
        with patch("hephae_api.routers.admin.zipcode_research.delete_run", new_callable=AsyncMock):
            response = client.delete("/api/zipcode-research/runs/r1")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Discovery Jobs endpoints
# ---------------------------------------------------------------------------

class TestDiscoveryJobs:
    """CRUD /api/admin/discovery-jobs"""

    def test_list_jobs(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.list_discovery_jobs", new_callable=AsyncMock, return_value=[]):
            response = client.get("/api/admin/discovery-jobs")
        assert response.status_code == 200
        assert response.json()["jobs"] == []

    def test_create_job(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.create_discovery_job", new_callable=AsyncMock, return_value="job-123"):
            response = client.post("/api/admin/discovery-jobs", json={
                "name": "Test Job",
                "targets": [{"zipCode": "07110", "businessTypes": ["restaurant"]}],
            })
        assert response.status_code == 200
        assert response.json()["jobId"] == "job-123"

    def test_create_job_empty_targets(self, client):
        response = client.post("/api/admin/discovery-jobs", json={
            "name": "Empty",
            "targets": [],
        })
        assert response.status_code == 400

    def test_get_job(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value={"id": "job-1", "status": "pending"}):
            response = client.get("/api/admin/discovery-jobs/job-1")
        assert response.status_code == 200

    def test_get_job_not_found(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/admin/discovery-jobs/nonexistent")
        assert response.status_code == 404

    def test_delete_pending_job(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value={"id": "j1", "status": "pending"}), \
             patch("hephae_api.routers.admin.discovery_jobs.cancel_job", new_callable=AsyncMock):
            response = client.delete("/api/admin/discovery-jobs/j1")
        assert response.status_code == 200

    def test_delete_completed_job(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value={"id": "j1", "status": "completed"}), \
             patch("hephae_api.routers.admin.discovery_jobs.delete_discovery_job", new_callable=AsyncMock):
            response = client.delete("/api/admin/discovery-jobs/j1")
        assert response.status_code == 200

    def test_delete_running_job_blocked(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value={"id": "j1", "status": "running"}):
            response = client.delete("/api/admin/discovery-jobs/j1")
        assert response.status_code == 409

    def test_run_job_not_found(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value=None):
            response = client.post("/api/admin/discovery-jobs/j1/run-now")
        assert response.status_code == 404

    def test_run_already_running_job(self, client):
        with patch("hephae_api.routers.admin.discovery_jobs.get_discovery_job", new_callable=AsyncMock, return_value={"id": "j1", "status": "running"}):
            response = client.post("/api/admin/discovery-jobs/j1/run-now")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Area Research endpoints
# ---------------------------------------------------------------------------

class TestAreaResearch:
    """POST/GET/DELETE /api/area-research"""

    def test_create_area_research(self, client):
        with patch("hephae_api.routers.admin.area_research.start_area_research", new_callable=AsyncMock, return_value={"areaId": "area-1"}):
            response = client.post("/api/area-research", json={
                "area": "Bergen County, NJ",
                "businessType": "restaurant",
            })
        assert response.status_code == 200
        assert response.json()["areaId"] == "area-1"

    def test_list_area_research(self, client):
        with patch("hephae_api.routers.admin.area_research.list_area_research", new_callable=AsyncMock, return_value=[{"id": "a1"}]):
            response = client.get("/api/area-research")
        assert response.status_code == 200

    def test_get_area_research(self, client):
        with patch("hephae_api.routers.admin.area_research.load_area_research", new_callable=AsyncMock, return_value={"id": "a1", "phase": "completed"}):
            response = client.get("/api/area-research/a1")
        assert response.status_code == 200

    def test_get_area_research_not_found(self, client):
        with patch("hephae_api.routers.admin.area_research.load_area_research", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/area-research/nonexistent")
        assert response.status_code == 404

    def test_delete_area_research(self, client):
        with patch("hephae_api.routers.admin.area_research.get_active_orchestrator", return_value=None), \
             patch("hephae_api.routers.admin.area_research.delete_area_research", new_callable=AsyncMock):
            response = client.delete("/api/area-research/a1")
        assert response.status_code == 200

    def test_delete_running_area_research_blocked(self, client):
        with patch("hephae_api.routers.admin.area_research.get_active_orchestrator", return_value=MagicMock()):
            response = client.delete("/api/area-research/a1")
        assert response.status_code == 400
        assert "running" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Sector Research endpoints
# ---------------------------------------------------------------------------

class TestSectorResearch:
    """POST/GET /api/sector-research"""

    def test_create_sector_research_new(self, client):
        with patch("hephae_api.routers.admin.sector_research.get_sector_research_for_type", new_callable=AsyncMock, return_value=None), \
             patch("hephae_api.routers.admin.sector_research.run_sector_research", new_callable=AsyncMock), \
             patch("hephae_api.routers.admin.sector_research.asyncio"):
            response = client.post("/api/sector-research", json={"sector": "pizza"})
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_create_sector_research_existing(self, client):
        existing = {"id": "sec-1", "sector": "pizza"}
        with patch("hephae_api.routers.admin.sector_research.get_sector_research_for_type", new_callable=AsyncMock, return_value=existing):
            response = client.post("/api/sector-research", json={"sector": "pizza"})
        assert response.status_code == 200
        assert response.json()["status"] == "existing"

    def test_list_sector_research(self, client):
        with patch("hephae_api.routers.admin.sector_research.list_sector_research", new_callable=AsyncMock, return_value=[]):
            response = client.get("/api/sector-research")
        assert response.status_code == 200

    def test_get_sector_research(self, client):
        with patch("hephae_api.routers.admin.sector_research.load_sector_research", new_callable=AsyncMock, return_value={"id": "s1"}):
            response = client.get("/api/sector-research/s1")
        assert response.status_code == 200

    def test_get_sector_research_not_found(self, client):
        with patch("hephae_api.routers.admin.sector_research.load_sector_research", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/sector-research/nonexistent")
        assert response.status_code == 404
