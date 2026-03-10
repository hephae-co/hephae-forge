"""Tests for Toolified Capabilities (Hub-and-Spoke)."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from backend.workflows.capabilities.tools import get_capability_tool, get_all_capability_tools
from google.adk.agents import AgentTool

@pytest.mark.asyncio
async def test_get_capability_tool_seo():
    """Verify SEO runner is correctly wrapped as an AgentTool."""
    with patch("backend.workflows.capabilities.registry.get_capability") as mock_get:
        mock_cap = MagicMock()
        mock_cap.name = "seo"
        mock_cap.display_name = "SEO Audit"
        mock_cap.runner = AsyncMock(return_value={"overallScore": 85})
        mock_cap.response_adapter = lambda x: {**x, "adapted": True}
        mock_get.return_value = mock_cap
        
        tool = get_capability_tool("seo")
        
        assert isinstance(tool, AgentTool)
        assert tool.name == "run_seo_analysis"
        
        # Test tool execution
        with patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock) as mock_biz:
            mock_biz.return_value = {"identity": {"name": "Test"}, "name": "Test"}
            result = await tool.fn(business_id="biz-123")
            
            assert result["overallScore"] == 85
            assert result["adapted"] is True
            mock_cap.runner.assert_called_once()

def test_get_all_capability_tools():
    """Verify we can retrieve all enabled tools."""
    with patch("backend.workflows.capabilities.registry.get_enabled_capabilities") as mock_list:
        mock_cap = MagicMock()
        mock_cap.name = "test"
        mock_list.return_value = [mock_cap]
        
        with patch("backend.workflows.capabilities.tools.get_capability_tool") as mock_get_tool:
            mock_get_tool.return_value = MagicMock(spec=AgentTool)
            tools = get_all_capability_tools()
            
            assert len(tools) == 1
            assert isinstance(tools[0], AgentTool)
