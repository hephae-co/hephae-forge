import pytest
from unittest.mock import patch, MagicMock, AsyncMock

try:
    from hephae_capabilities.discovery import scan_zipcode, BusinessItem
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)

try:
    from backend.agents.analyst import run_deep_dive
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)

@pytest.mark.asyncio
@patch("hephae_capabilities.discovery.firestore_service.get_businesses_in_zipcode")
async def test_scan_zipcode_cached(mock_get_cached):
    mock_get_cached.return_value = [{"name": "Cached Biz", "address": "123 St", "docId": "cached-biz"}]

    results = await scan_zipcode("10001")

    assert len(results) == 1
    assert results[0].name == "Cached Biz"
    mock_get_cached.assert_called_with("10001")

@pytest.mark.asyncio
@patch("hephae_capabilities.discovery.firestore_service")
async def test_scan_zipcode_cached_enriched(mock_fs):
    """Cache hit with enriched data returns full BusinessItem fields."""
    mock_fs.get_businesses_in_zipcode.return_value = [
        {
            "name": "Rich Biz",
            "address": "456 Ave",
            "docId": "rich-biz",
            "zipCode": "10001",
            "phone": "212-555-0100",
            "email": "info@richbiz.com",
            "confidence": 0.85,
        }
    ]

    results = await scan_zipcode("10001")

    assert len(results) == 1
    assert results[0].name == "Rich Biz"
    assert results[0].phone == "212-555-0100"
    assert results[0].confidence == 0.85

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
@patch("backend.agents.analyst.firestore_service.update_latest_outputs")
async def test_run_deep_dive_success(mock_update, mock_post):
    # Mock responses for 3 API calls
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"score": 90, "summary": "Great"}
    mock_post.return_value = mock_resp

    identity = {"name": "Test Biz", "docId": "test-biz"}
    results = await run_deep_dive(identity)

    assert "trafficForecast" in results
    assert "seoAudit" in results
    assert "competitiveAnalysis" in results
    mock_update.assert_called_once()
