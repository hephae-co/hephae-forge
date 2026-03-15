"""
Tier 5: Live Tool Probes (Monitoring).

Periodically verifies that external tools (Search, Crawl, Pagespeed)
are still functional and haven't broken due to external site changes.
"""

from __future__ import annotations

import pytest
import logging
from hephae_agents.discovery.tools import locator_tool, crawler_tool
from hephae_agents.seo_auditor.tools import pagespeed_tool

logger = logging.getLogger(__name__)

@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.asyncio
async def test_live_probe_google_search():
    """Verify that LocatorAgent can still find a 'Golden Business' via Google Search."""
    # Using 'Nom Wah Tea Parlor' as a highly stable result
    result = await locator_tool.run_async(query="Nom Wah Tea Parlor NYC official website")
    
    assert result and "nomwah.com" in str(result).lower(), \
        f"Search probe failed: Could not find Nom Wah official site. Result: {result}"
    logger.info("Live Search Probe: SUCCESS")

@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.asyncio
async def test_live_probe_crawler():
    """Verify that SiteCrawler can still extract content from a stable live URL."""
    # Using a simple, fast-loading URL
    result = await crawler_tool.run_async(url="https://nomwah.com/")
    
    # We expect some structured output from Crawl4AI
    assert result and "Nom Wah" in str(result), \
        f"Crawler probe failed: Could not extract 'Nom Wah' from official site. Result: {result}"
    logger.info("Live Crawler Probe: SUCCESS")

@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.asyncio
async def test_live_probe_pagespeed():
    """Verify that Pagespeed tool is still responding."""
    result = await pagespeed_tool.run_async(url="https://nomwah.com/")
    
    assert result and "score" in str(result).lower() and "error" not in str(result).lower(), \
        f"Pagespeed probe failed. Result: {result}"
    logger.info("Live Pagespeed Probe: SUCCESS")
