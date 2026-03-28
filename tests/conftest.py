"""
Shared pytest configuration for backend tests.

Registers custom markers used across the test suite:
  - functional: tests that invoke real Gemini agents (require GEMINI_API_KEY)
  - integration: tests that require live Firestore / network / browser
  - needs_browser: tests requiring Playwright/crawl4ai (skip on Cloud Run)
"""

from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "functional: real runner calls that invoke Gemini agents (requires GEMINI_API_KEY)",
    )
    config.addinivalue_line(
        "markers",
        "integration: real API integration tests (requires GEMINI_API_KEY and live DB)",
    )
    config.addinivalue_line(
        "markers",
        "needs_browser: tests that need Playwright/crawl4ai (skip on Cloud Run)",
    )


def pytest_collection_modifyitems(config, items):
    if not os.environ.get("GEMINI_API_KEY"):
        skip_gemini = pytest.mark.skip(reason="GEMINI_API_KEY not set")
        for item in items:
            if "functional" in item.keywords or "integration" in item.keywords:
                item.add_marker(skip_gemini)

    if bool(os.environ.get("K_SERVICE")):
        skip_browser = pytest.mark.skip(
            reason="Cloud Run Service: no Playwright browser — use Cloud Run Job instead"
        )
        for item in items:
            if "needs_browser" in item.keywords:
                item.add_marker(skip_browser)
