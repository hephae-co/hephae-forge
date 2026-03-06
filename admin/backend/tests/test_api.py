import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from backend.main import app
from backend.config import settings

client = TestClient(app)

@pytest.fixture
def mock_auth_header():
    return {"Authorization": f"Bearer {settings.CRON_SECRET}"}

@patch("backend.main.scan_zipcode", new_callable=AsyncMock)
@patch("backend.main.run_deep_dive", new_callable=AsyncMock)
def test_cron_run_analysis_success(mock_deep_dive, mock_scan, mock_auth_header):
    # Mock data
    mock_biz = MagicMock()
    mock_biz.name = "Test Biz"
    mock_biz.model_dump.return_value = {"name": "Test Biz", "docId": "test-biz"}
    mock_scan.return_value = [mock_biz]
    mock_deep_dive.return_value = {"success": True}

    response = client.get("/api/cron/run-analysis?zip=10001", headers=mock_auth_header)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["report"]) == 1
    assert data["report"][0]["business"] == "Test Biz"

def test_cron_run_analysis_unauthorized():
    response = client.get("/api/cron/run-analysis?zip=10001", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401

@patch("backend.main.test_runner.run_all_tests", new_callable=AsyncMock)
def test_run_tests_success(mock_run_all):
    mock_run_all.return_value = {"runId": "run_123", "totalTests": 10}
    response = client.post("/api/run-tests")
    assert response.status_code == 200
    assert response.json()["runId"] == "run_123"

def test_get_test_runs_empty():
    response = client.get("/api/run-tests")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Zipcode Research API endpoints
# ---------------------------------------------------------------------------

@patch("backend.main.run_zipcode_research", new_callable=AsyncMock)
def test_post_zipcode_research_success(mock_run):
    mock_report = {
        "summary": "Test zip 07110",
        "zip_code": "07110",
        "sections": {"geography": {"title": "Geo", "content": "NJ", "key_facts": []}},
        "sources": [],
    }
    mock_run.return_value = mock_report

    response = client.post("/api/zipcode-research/07110")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["report"]["zip_code"] == "07110"
    assert data["report"]["summary"] == "Test zip 07110"
    mock_run.assert_called_once_with("07110")


@patch("backend.main.run_zipcode_research", new_callable=AsyncMock)
def test_post_zipcode_research_pipeline_error(mock_run):
    mock_run.side_effect = Exception("Pipeline timeout")

    response = client.post("/api/zipcode-research/10001")

    assert response.status_code == 500
    assert "Pipeline timeout" in response.json()["detail"]


def test_post_zipcode_research_invalid_zip():
    response = client.post("/api/zipcode-research/abc")
    assert response.status_code == 422


def test_post_zipcode_research_too_short():
    response = client.post("/api/zipcode-research/123")
    assert response.status_code == 422


@patch("backend.main.firestore_service")
def test_get_zipcode_research_cached(mock_fs):
    cached = {
        "summary": "Cached for 20002",
        "zip_code": "20002",
        "sections": {},
        "sources": [],
    }
    mock_fs.get_zipcode_research.return_value = cached

    response = client.get("/api/zipcode-research/20002")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["cached"] is True
    assert data["report"]["zip_code"] == "20002"
    mock_fs.get_zipcode_research.assert_called_once_with("20002")


@patch("backend.main.firestore_service")
def test_get_zipcode_research_not_cached(mock_fs):
    mock_fs.get_zipcode_research.return_value = None

    response = client.get("/api/zipcode-research/30303")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["cached"] is False
    assert data["report"] is None


def test_get_zipcode_research_invalid_zip():
    response = client.get("/api/zipcode-research/ABCDE")
    assert response.status_code == 422
