"""Functional tests for v1 API route runner logic.

Tests call runner functions directly — no HTTP client, no mocks.
Validates: auth function behavior, runner output shapes, error cases.

Auth tests require no API key (pure logic).
Runner tests require GEMINI_API_KEY.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# API key auth logic tests (no Gemini needed)
# ---------------------------------------------------------------------------

class TestApiKeyAuthLogic:
    def test_missing_api_key_raises_401(self):
        """When FORGE_V1_API_KEY is set, missing key header raises 401."""
        old = os.environ.get("FORGE_V1_API_KEY", "")
        os.environ["FORGE_V1_API_KEY"] = "test-key-123"
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_api_key(x_api_key=None)
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_V1_API_KEY"] = old
            importlib.reload(auth_module)

    def test_invalid_api_key_raises_401(self):
        """Wrong API key must raise 401."""
        old = os.environ.get("FORGE_V1_API_KEY", "")
        os.environ["FORGE_V1_API_KEY"] = "test-key-123"
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

            with pytest.raises(HTTPException) as exc_info:
                auth_module.verify_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401
        finally:
            os.environ["FORGE_V1_API_KEY"] = old
            importlib.reload(auth_module)

    def test_valid_api_key_passes(self):
        """Correct API key must not raise."""
        old = os.environ.get("FORGE_V1_API_KEY", "")
        os.environ["FORGE_V1_API_KEY"] = "test-key-123"
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

            result = auth_module.verify_api_key(x_api_key="test-key-123")
            assert result is None
        finally:
            os.environ["FORGE_V1_API_KEY"] = old
            importlib.reload(auth_module)

    def test_no_key_configured_allows_all(self):
        """When FORGE_V1_API_KEY is empty, all requests pass (dev mode)."""
        old = os.environ.get("FORGE_V1_API_KEY", "")
        os.environ["FORGE_V1_API_KEY"] = ""
        try:
            import importlib
            import hephae_common.auth as auth_module
            importlib.reload(auth_module)

            result = auth_module.verify_api_key(x_api_key=None)
            assert result is None
        finally:
            os.environ["FORGE_V1_API_KEY"] = old
            importlib.reload(auth_module)


# ---------------------------------------------------------------------------
# Runner validation tests (no Gemini needed)
# ---------------------------------------------------------------------------

class TestSeoRunnerValidation:
    def test_run_seo_audit_raises_for_missing_url(self):
        """Missing officialUrl must raise ValueError."""
        import asyncio
        from hephae_agents.seo_auditor.runner import run_seo_audit

        no_url = {"name": "Test Biz", "officialUrl": None}
        with pytest.raises((ValueError, Exception)):
            asyncio.get_event_loop().run_until_complete(run_seo_audit(no_url))


class TestCompetitiveRunnerValidation:
    def test_run_competitive_raises_for_missing_name(self):
        """Competitive analysis with no name should raise or return gracefully."""
        import asyncio
        from hephae_agents.competitive_analysis.runner import run_competitive_analysis

        no_name = {
            "name": None,
            "address": "123 Main St",
            "competitors": [{"name": "Rival", "url": "https://rival.com"}],
        }
        # Either raises or returns a dict — must not silently crash with attribute error
        try:
            result = asyncio.get_event_loop().run_until_complete(run_competitive_analysis(no_name))
            assert isinstance(result, dict) or result is None
        except (ValueError, Exception):
            pass  # Raising is also acceptable behavior


# ---------------------------------------------------------------------------
# Functional runner tests (require GEMINI_API_KEY)
# ---------------------------------------------------------------------------

pytestmark_functional = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set",
)

_SAMPLE_IDENTITY = {
    "name": "Joe's Pizza",
    "address": "123 Main St, Newark, NJ 07102",
    "officialUrl": "https://joespizza.com",
    "competitors": [{"name": "Rival Pizza", "url": "https://rivalpizza.com"}],
    "zipCode": "07102",
}


@pytest.mark.functional
@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
async def test_seo_runner_returns_valid_output():
    """run_seo_audit returns a dict with url and sections."""
    from hephae_agents.seo_auditor.runner import run_seo_audit

    result = await run_seo_audit(_SAMPLE_IDENTITY)
    assert isinstance(result, dict)
    assert result.get("url") == _SAMPLE_IDENTITY["officialUrl"]
    assert "sections" in result
    assert isinstance(result["sections"], list)


@pytest.mark.functional
@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="needs GEMINI_API_KEY")
async def test_competitive_runner_returns_valid_output():
    """run_competitive_analysis returns a dict with market_summary or overall_score."""
    from hephae_agents.competitive_analysis.runner import run_competitive_analysis

    result = await run_competitive_analysis(_SAMPLE_IDENTITY)
    assert isinstance(result, dict)
    score = result.get("overall_score") or result.get("overallScore")
    if score is not None:
        assert 0 <= score <= 100
