import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from hephae_agents.outreach.communicator import draft_and_send_outreach
from hephae_api.workflows.test_runner import test_runner
from hephae_agents.evaluators.seo_evaluator import SeoEvaluatorAgent

@pytest.mark.asyncio
@patch("hephae_agents.outreach.communicator.get_db")
@patch("hephae_agents.outreach.communicator.get_business", new_callable=AsyncMock)
@patch("hephae_agents.outreach.communicator.run_agent_to_text", new_callable=AsyncMock)
@patch("hephae_agents.outreach.communicator.send_email", new_callable=AsyncMock)
async def test_draft_and_send_outreach_success(mock_send_email, mock_run_agent, mock_get_biz, mock_get_db):
    # Mock business data
    mock_get_biz.return_value = {
        "identity": {
            "name": "Test Cafe",
            "email": "test@cafe.com"
        }
    }

    # Mock agent output
    mock_run_agent.return_value = "Hello Test Cafe, here are your insights. " * 5  # >50 chars

    # Mock Firestore db
    mock_db = MagicMock()
    mock_draft_doc = MagicMock()
    mock_draft_doc.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = mock_draft_doc
    mock_db.collection.return_value.document.return_value.update.return_value = None
    mock_get_db.return_value = mock_db

    result = await draft_and_send_outreach(business_slug="test-cafe", channel="email")

    assert result["success"] is True
    assert result["sentTo"] == "test@cafe.com"
    mock_send_email.assert_called_once()

@pytest.mark.asyncio
@patch("hephae_agents.margin_analyzer.runner.run_margin_analysis", new_callable=AsyncMock, return_value={"items": []})
@patch("hephae_agents.competitive_analysis.runner.run_competitive_analysis", new_callable=AsyncMock, return_value={"competitors": []})
@patch("hephae_agents.traffic_forecaster.runner.run_traffic_forecast", new_callable=AsyncMock, return_value={"forecast": []})
@patch("hephae_agents.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value={"overallScore": 85})
@patch("hephae_api.workflows.test_runner.HephaeTestRunner.evaluate_with_agent", new_callable=AsyncMock)
async def test_run_all_tests_success(mock_evaluate, mock_seo, mock_traffic, mock_competitive, mock_margin):
    # Mock evaluation — all pass
    mock_evaluate.return_value = {"score": 95, "isHallucinated": False, "issues": []}

    with patch("hephae_db.firestore.test_runs.save_test_run", new_callable=AsyncMock):
        summary = await test_runner.run_all_tests()

    assert summary["totalTests"] > 0
    assert summary["passedTests"] > 0
    assert "results" in summary

@pytest.mark.asyncio
async def test_seo_evaluator_agent_initialization():
    assert SeoEvaluatorAgent.name == "seo_evaluator"
    assert "SEO Quality Assurance" in SeoEvaluatorAgent.instruction
