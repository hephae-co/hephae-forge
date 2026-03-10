"""Tests for ADK helper functions."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pydantic import BaseModel
from hephae_common.adk_helpers import run_agent_to_json
from google.adk.agents import LlmAgent

class MockResponse(BaseModel):
    name: str
    score: int

@pytest.mark.asyncio
async def test_run_agent_to_json_native_mode():
    """Verify run_agent_to_json forces native JSON mode and injects examples."""
    agent = LlmAgent(name="test_agent", instruction="base")
    
    # Mock Example Store
    with patch("hephae_db.eval.example_store.example_store.inject_examples_to_instruction", new_callable=AsyncMock) as mock_inject:
        mock_run = AsyncMock()
        # Mocking the runner stream
        mock_event = MagicMock()
        mock_event.content.parts = [MagicMock(text='{"name": "test", "score": 90}', thought=False)]
        
        async def mock_run_async(*args, **kwargs):
            yield mock_event

        mock_inject.return_value = "base + examples"
        
        with patch("google.adk.runners.Runner.run_async", side_effect=mock_run_async):
            with patch("hephae_common.adk_helpers._session_service.create_session", new_callable=AsyncMock):
                result = await run_agent_to_json(agent, "test prompt", response_schema=MockResponse)
                
                # Check Example Injection
                mock_inject.assert_called_once()
                
                # Check Validation
                assert isinstance(result, MockResponse)
                assert result.name == "test"
                assert result.score == 90

@pytest.mark.asyncio
async def test_run_agent_to_json_no_markdown_strip_needed():
    """Verify P0.3: No more manual regex hacks needed."""
    agent = LlmAgent(name="test_agent", instruction="base")
    
    mock_event = MagicMock()
    # Native JSON mode returns raw JSON, no ```json fences
    mock_event.content.parts = [MagicMock(text='{"key": "val"}', thought=False)]
    
    async def mock_run_async(*args, **kwargs):
        yield mock_event

    with patch("google.adk.runners.Runner.run_async", side_effect=mock_run_async):
        with patch("hephae_common.adk_helpers._session_service.create_session", new_callable=AsyncMock):
            with patch("hephae_db.eval.example_store.example_store.inject_examples_to_instruction", new_callable=AsyncMock) as mock_inject:
                mock_inject.return_value = "base"
                result = await run_agent_to_json(agent, "prompt")
                
                assert result == {"key": "val"}
