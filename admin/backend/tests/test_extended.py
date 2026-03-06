import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from agents.outreach import draft_and_send_outreach, CommunicatorInput
from services.test_runner import test_runner
from agents.evaluators import seo_evaluator_agent

@pytest.mark.asyncio
@patch("agents.outreach.firestore_service.get_business_by_id")
@patch("google.adk.Runner.run_async")
@patch("agents.outreach.send_email", new_callable=AsyncMock)
async def test_draft_and_send_outreach_success(mock_send_email, mock_runner_run, mock_get_biz):
    # Mock business data
    mock_get_biz.return_value = {
        "identity": {
            "name": "Test Cafe",
            "email": "test@cafe.com"
        }
    }
    
    # Mock runner event stream
    mock_part = MagicMock()
    mock_part.text = json.dumps({
        "subject": "Hello",
        "body": "This is a test message"
    })
    
    mock_event = MagicMock()
    mock_event.content.parts = [mock_part]
    
    async def mock_generator(*args, **kwargs):
        yield mock_event
        
    mock_runner_run.side_effect = mock_generator
    
    input_data = CommunicatorInput(
        identity={"name": "Test Cafe", "docId": "test-cafe"},
        channel="email"
    )
    
    result = await draft_and_send_outreach(input_data)
    
    assert result.success is True
    assert result.sentTo == "test@cafe.com"
    mock_send_email.assert_called_once()

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("services.test_runner.HephaeAdminRunner.evaluate_with_agent", new_callable=AsyncMock)
async def test_run_all_tests_success(mock_evaluate, mock_post):
    # Mock API response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"score": 90}
    mock_post.return_value = mock_resp
    
    # Mock evaluation
    mock_evaluate.return_value = {"score": 95, "isHallucinated": False, "issues": []}
    
    summary = await test_runner.run_all_tests()
    
    assert summary["totalTests"] > 0
    assert summary["passedTests"] > 0
    assert "results" in summary

@pytest.mark.asyncio
async def test_seo_evaluator_agent_initialization():
    assert seo_evaluator_agent.name == "seo_evaluator"
    assert "SEO Quality Assurance" in seo_evaluator_agent.instruction
