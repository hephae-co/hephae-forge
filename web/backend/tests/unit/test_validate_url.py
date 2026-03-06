"""Unit tests for validate_url shared tool (mock httpx)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.agents.shared_tools.validate_url import (
    validate_url,
    validate_urls_batch,
    _check_pattern,
    _http_check,
    PLATFORM_PATTERNS,
    SOCIAL_403_PLATFORMS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, url: str = ""):
    """Create a mock httpx.Response with the given status code."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url or "https://example.com"
    return resp


def _mock_client(resp):
    """Create mock httpx.AsyncClient returning resp on HEAD."""
    client = AsyncMock()
    client.head = AsyncMock(return_value=resp)
    client.get = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ============================================================================
# Pattern validation
# ============================================================================

class TestPatternValidation:
    def test_valid_instagram_pattern(self):
        assert _check_pattern("https://instagram.com/bosphorus_nj", "instagram")
        assert _check_pattern("https://www.instagram.com/bosphorus_nj/", "instagram")

    def test_invalid_instagram_pattern(self):
        assert not _check_pattern("https://notinstagram.com/bosphorus", "instagram")
        assert not _check_pattern("https://instagram.com/", "instagram")

    def test_valid_facebook_pattern(self):
        assert _check_pattern("https://facebook.com/BosphorusNutley", "facebook")
        assert _check_pattern("https://www.facebook.com/BosphorusNutley", "facebook")
        assert _check_pattern("https://m.facebook.com/BosphorusNutley", "facebook")

    def test_invalid_facebook_pattern(self):
        assert not _check_pattern("https://fakebook.com/test", "facebook")

    def test_valid_twitter_pattern(self):
        assert _check_pattern("https://twitter.com/bosphorus_nj", "twitter")
        assert _check_pattern("https://x.com/bosphorus_nj", "twitter")

    def test_valid_yelp_pattern(self):
        assert _check_pattern("https://www.yelp.com/biz/bosphorus-nutley", "yelp")

    def test_invalid_yelp_pattern(self):
        assert not _check_pattern("https://yelp.com/user/someone", "yelp")

    def test_valid_doordash_pattern(self):
        assert _check_pattern("https://www.doordash.com/store/bosphorus-123", "doordash")

    def test_invalid_doordash_pattern(self):
        assert not _check_pattern("https://doordash.com/business/bosphorus", "doordash")

    def test_valid_google_maps_pattern(self):
        assert _check_pattern("https://www.google.com/maps/place/Bosphorus", "google_maps")
        assert _check_pattern("https://maps.google.com/something", "google_maps")

    def test_unknown_platform_always_passes(self):
        assert _check_pattern("https://anything.com/whatever", "")
        assert _check_pattern("https://anything.com/whatever", "unknown_platform")

    def test_valid_delivery_platform_patterns(self):
        assert _check_pattern("https://www.grubhub.com/restaurant/bosphorus-123", "grubhub")
        assert _check_pattern("https://www.ubereats.com/store/bosphorus-nyc", "ubereats")
        assert _check_pattern("https://www.seamless.com/menu/bosphorus-nutley", "seamless")
        assert _check_pattern("https://www.toasttab.com/bosphorus-nutley", "toasttab")

    def test_tiktok_requires_at_sign(self):
        assert _check_pattern("https://www.tiktok.com/@bosphorus_nj", "tiktok")
        assert not _check_pattern("https://www.tiktok.com/bosphorus_nj", "tiktok")


# ============================================================================
# HTTP validation (mocked httpx)
# ============================================================================

class TestHttpValidation:
    @pytest.mark.asyncio
    async def test_200_returns_valid(self):
        resp = _mock_response(200, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "valid"
        assert result["http_code"] == 200

    @pytest.mark.asyncio
    async def test_301_returns_valid(self):
        resp = _mock_response(301, "https://example.com/new")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "valid"

    @pytest.mark.asyncio
    async def test_404_returns_invalid(self):
        resp = _mock_response(404, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "invalid"
        assert result["http_code"] == 404
        assert "not found" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_410_returns_invalid(self):
        resp = _mock_response(410, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "invalid"
        assert result["http_code"] == 410

    @pytest.mark.asyncio
    async def test_403_social_returns_unverifiable(self):
        """Social media platforms that return 403 due to bot protection."""
        resp = _mock_response(403, "https://instagram.com/test_user")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://instagram.com/test_user", "instagram")
        assert result["status"] == "unverifiable"
        assert result["http_code"] == 403
        assert "blocks automated" in result["reason"].lower() or "403" in result["reason"]

    @pytest.mark.asyncio
    async def test_403_non_social_returns_unverifiable(self):
        """Non-social 403 is unverifiable, not invalid."""
        resp = _mock_response(403, "https://example.com/menu")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com/menu", "")
        assert result["status"] == "unverifiable"
        assert result["http_code"] == 403

    @pytest.mark.asyncio
    async def test_500_returns_unverifiable(self):
        resp = _mock_response(500, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "unverifiable"
        assert result["http_code"] == 500

    @pytest.mark.asyncio
    async def test_timeout_returns_unverifiable(self):
        client = AsyncMock()
        client.head = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "unverifiable"
        assert result["http_code"] is None


# ============================================================================
# Combined pattern + HTTP
# ============================================================================

class TestCombinedValidation:
    @pytest.mark.asyncio
    async def test_pattern_mismatch_skips_http(self):
        """If the URL doesn't match the platform pattern, HTTP is never called."""
        result = await validate_url("https://notinstagram.com/fake", "instagram")
        assert result["status"] == "pattern_mismatch"
        assert result["pattern_ok"] is False
        assert result["http_code"] is None

    @pytest.mark.asyncio
    async def test_empty_url_returns_invalid(self):
        result = await validate_url("", "instagram")
        assert result["status"] == "invalid"
        assert result["pattern_ok"] is False

    @pytest.mark.asyncio
    async def test_none_url_returns_invalid(self):
        result = await validate_url(None, "")  # type: ignore[arg-type]
        assert result["status"] == "invalid"

    @pytest.mark.asyncio
    async def test_result_shape(self):
        """Every result must have all expected keys."""
        resp = _mock_response(200, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        expected_keys = {"url", "status", "http_code", "redirected_to", "pattern_ok", "reason"}
        assert set(result.keys()) == expected_keys


# ============================================================================
# Batch validation
# ============================================================================

class TestBatchValidation:
    @pytest.mark.asyncio
    async def test_validates_multiple_urls(self):
        resp = _mock_response(200, "https://example.com")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            results = await validate_urls_batch([
                {"url": "https://example.com", "platform": ""},
                {"url": "https://example.com/page2", "platform": ""},
            ])
        assert len(results) == 2
        assert all(r["status"] == "valid" for r in results)

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        results = await validate_urls_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_handles_missing_keys(self):
        """If url or platform key is missing, should default to empty string."""
        result = await validate_urls_batch([{}])
        assert len(result) == 1
        assert result[0]["status"] == "invalid"


# ============================================================================
# Edge cases
# ============================================================================

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_405_triggers_get_fallback(self):
        """If HEAD returns 405, should retry with GET."""
        head_resp = _mock_response(405, "https://example.com")
        get_resp = _mock_response(200, "https://example.com")

        client = AsyncMock()
        client.head = AsyncMock(return_value=head_resp)
        client.get = AsyncMock(return_value=get_resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "valid"
        assert result["http_code"] == 200

    @pytest.mark.asyncio
    async def test_redirect_captured(self):
        """Redirects should be captured in redirected_to field."""
        resp = _mock_response(200, "https://example.com/final-page")
        client = _mock_client(resp)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com/original", "")
        assert result["redirected_to"] == "https://example.com/final-page"

    @pytest.mark.asyncio
    async def test_connection_error_returns_unverifiable(self):
        client = AsyncMock()
        client.head = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        with patch("backend.agents.shared_tools.validate_url.httpx.AsyncClient", return_value=client):
            result = await validate_url("https://example.com", "")
        assert result["status"] == "unverifiable"
        assert result["http_code"] is None
