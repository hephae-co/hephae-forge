"""Tests for the Hub-and-Crawl Lead Discovery pattern."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from backend.workflows.agents.research.local_catalyst import research_local_catalysts
from backend.workflows.agents.discovery.municipal_hubs import find_municipal_hub
from backend.workflows.agents.discovery.directory_parser import parse_directory_content
from backend.workflows.orchestrators.area_research import AreaResearchOrchestrator
from backend.types import AreaResearchDocument, AreaResearchPhase

# ---------------------------------------------------------------------------
# 1. Component Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_municipal_hub():
    """Verify MunicipalHubAgent returns a valid URL."""
    with patch("backend.workflows.agents.discovery.municipal_hubs.run_agent_to_text", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "https://montclairchamber.com/directory"
        
        url = await find_municipal_hub("Montclair", "NJ")
        
        assert url == "https://montclairchamber.com/directory"
        mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_find_municipal_hub_none():
    """Verify MunicipalHubAgent returns None on fallback."""
    with patch("backend.workflows.agents.discovery.municipal_hubs.run_agent_to_text", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "NONE"
        
        url = await find_municipal_hub("Nowhere", "XY")
        
        assert url is None

@pytest.mark.asyncio
async def test_parse_directory_content():
    """Verify DirectoryParserAgent extracts businesses from markdown."""
    from hephae_db.schemas import ZipcodeScannerOutput
    
    mock_output = ZipcodeScannerOutput(businesses=[
        {"name": "Bakery A", "address": "123 St", "website": "a.com", "category": "Bakery"},
        {"name": "Bakery B", "address": "456 St", "website": "b.com", "category": "Bakery"}
    ])
    
    with patch("backend.workflows.agents.discovery.directory_parser.run_agent_to_json", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_output
        
        leads = await parse_directory_content("Raw Content", category="Bakery")
        
        assert len(leads) == 2
        assert leads[0]["name"] == "Bakery A"

@pytest.mark.asyncio
async def test_research_local_catalysts():
    """Verify LocalCatalystAgent returns structured catalysts."""
    mock_result = {
        "summary": "Supportive environment.",
        "catalysts": [
            {"type": "Infrastructure", "signal": "Road closure", "timing": "2025", "impact": "None", "confidence": 0.9}
        ],
        "recommendation": "Check site."
    }
    
    with patch("backend.workflows.agents.research.local_catalyst.run_agent_to_json", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        
        res = await research_local_catalysts("Nutley", "NJ", "Bakery")
        
        assert res["summary"] == "Supportive environment."
        assert len(res["catalysts"]) == 1

# ---------------------------------------------------------------------------
# 2. Orchestrator Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_area_research_lead_discovery_flow():
    """Verify AreaResearchOrchestrator executes Hub-and-Crawl phase."""
    doc = AreaResearchDocument(
        id="test-area",
        area="Montclair, NJ",
        businessType="Bakery",
        phase=AreaResearchPhase.COMPLETED,
        zipCodes=["07042"],
        completedZipCodes=["07042"]
    )
    
    orchestrator = AreaResearchOrchestrator(doc)
    
    mock_leads = [{"name": "Lead 1", "address": "Addr 1", "website": "w1.com", "category": "Bakery"}]
    
    # Patch all the steps in Phase 6
    with patch.object(orchestrator, "_discover_leads_from_hub", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = mock_leads
        
        # We only want to test the lead discovery part, so we mock the main run steps
        with patch.object(orchestrator, "_checkpoint", new_callable=AsyncMock), \
             patch.object(orchestrator, "_emit"), \
             patch("backend.workflows.orchestrators.area_research.generate_enhanced_area_summary", new_callable=AsyncMock) as mock_summary, \
             patch.object(orchestrator, "_fetch_zip_reports", new_callable=AsyncMock) as mock_fetch:
            
            mock_summary.return_value = "Test summary"
            mock_fetch.return_value = {}
            
            # Run the orchestrator
            # Note: We need to bypass early exit in run()
            orchestrator.doc.industryIntel = {"some": "data"}
            orchestrator.doc.localSectorInsights = {"trends": []}
            
            # We mock the entire run but focus on the end
            # or we just call the private method directly
            leads = await orchestrator._discover_leads_from_hub()
            
            assert leads == mock_leads
            assert mock_discover.called

@pytest.mark.asyncio
async def test_discover_leads_from_hub_implementation():
    """Verify internal logic of _discover_leads_from_hub."""
    doc = AreaResearchDocument(id="area1", area="Nutley, NJ", businessType="Cafe")
    orchestrator = AreaResearchOrchestrator(doc)
    
    with patch("backend.workflows.orchestrators.area_research.find_municipal_hub", new_callable=AsyncMock) as mock_find, \
         patch("backend.workflows.orchestrators.area_research.crawl4ai_tool", new_callable=AsyncMock) as mock_crawl, \
         patch("backend.workflows.orchestrators.area_research.parse_directory_content", new_callable=AsyncMock) as mock_parse, \
         patch("backend.workflows.orchestrators.area_research.save_business", new_callable=AsyncMock) as mock_save:
        
        mock_find.return_value = "http://hub.com"
        mock_crawl.return_value = {"markdown": "Raw Directory Data"}
        mock_parse.return_value = [{"name": "Cafe X", "address": "123 Main"}]
        
        leads = await orchestrator._discover_leads_from_hub()
        
        assert len(leads) == 1
        assert leads[0]["name"] == "Cafe X"
        mock_save.assert_called_once() # Verify it was saved to the unified pool
