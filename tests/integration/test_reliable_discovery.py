"""Targeted integration tests for reliable website and contact discovery."""

import pytest
import asyncio
import logging
import os
from hephae_agents.discovery.runner import run_discovery
from apps.api.hephae_api.workflows.phases.enrichment import _find_website

# Configure logging to see agent progress
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test targets from Nutley, NJ (07110)
# These are known to have various digital footprints
TARGETS = [
    {"name": "Bella Luce", "address": "507 Franklin Ave, Nutley, NJ 07110"},
    {"name": "Mamma Mia's Pizza", "address": "307 Bloomfield Ave, Nutley, NJ 07110"},
    {"name": "Sugar Tree Cafe", "address": "358 Passaic Ave, Nutley, NJ 07110"},
]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_targeted_website_discovery():
    """Test if _find_website finds the correct URLs using the new snippet strategy."""
    results = []
    for target in TARGETS:
        logger.info(f"Testing website discovery for: {target['name']}")
        url = await _find_website(target["name"], target["address"])
        logger.info(f"RESULT for {target['name']}: {url}")
        results.append({"name": target["name"], "url": url})
    
    # Assert that we found at least some URLs
    found_urls = [r["url"] for r in results if r["url"]]
    assert len(found_urls) > 0
    for r in results:
        print(f"Business: {r['name']}, URL: {r['url']}")

@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_contact_discovery_reliability():
    """Test full discovery pipeline for contact info reliability (no gating)."""
    results = []
    for target in TARGETS:
        print(f"\n[TEST] Processing: {target['name']}...")
        
        # First find the website
        url = await _find_website(target["name"], target["address"])
        print(f"[TEST] FOUND URL: {url}")
        
        identity = {
            "name": target["name"],
            "address": target["address"],
            "officialUrl": url
        }
        
        print(f"[TEST] Running full discovery for: {target['name']}")
        result = await run_discovery(identity)
        
        if result.get("discoveryAborted"):
            print(f"[TEST] Aborted: {result.get('discoveryAbortReason')}")
            results.append({"name": target["name"], "success": False, "reason": "aborted"})
            continue

        print(f"[TEST] Contact Result for {target['name']}:")
        print(f"  Email: {result.get('email')} ({result.get('emailStatus')})")
        print(f"  Phone: {result.get('phone')}")
        print(f"  Contact Form: {result.get('contactFormUrl')} ({result.get('contactFormStatus')})")
        
        has_contact = bool(result.get("email") or result.get("contactFormUrl") or result.get("phone"))
        results.append({"name": target["name"], "success": has_contact})

    success_count = len([r for r in results if r["success"]])
    print(f"\n[TEST] FINAL SUCCESS RATE: {success_count}/{len(results)}")
    assert success_count > 0
    
    # Check for platform email blacklist (negative test)
    banned_domains = ["@wix.com", "@shopify.com", "@squarespace.com"]
    if result.get("email"):
        assert not any(domain in result["email"] for domain in banned_domains)

if __name__ == "__main__":
    # Allow running this script directly for quick debugging
    asyncio.run(test_targeted_website_discovery())
