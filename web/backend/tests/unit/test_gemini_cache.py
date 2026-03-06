"""
Unit tests for backend/lib/gemini_cache.py

Covers: cache creation, cache registry, cache deletion, TTL behavior.
"""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from backend.lib.gemini_cache import (
    get_or_create_cache,
    delete_cache,
    clear_cache_registry,
    _cache_registry,
    _store_cached_name,
    _get_cached_name,
)
from backend.lib.business_context import BusinessContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_registry():
    clear_cache_registry()
    yield
    clear_cache_registry()


def _make_ctx(slug="test-biz", context_size=5000):
    """Create a BusinessContext with enough text for caching."""
    ctx = BusinessContext(
        slug=slug,
        identity={"name": "Test Biz", "address": "123 Main St", "data": "x" * context_size},
    )
    return ctx


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

class TestCacheRegistry:
    def test_store_and_get(self):
        _store_cached_name("slug-a", "model-1", "cache/name/123")
        assert _get_cached_name("slug-a", "model-1") == "cache/name/123"

    def test_get_missing(self):
        assert _get_cached_name("nonexistent", "model-1") is None

    def test_clear_specific_slug(self):
        _store_cached_name("slug-a", "model-1", "cache/a1")
        _store_cached_name("slug-a", "model-2", "cache/a2")
        _store_cached_name("slug-b", "model-1", "cache/b1")
        clear_cache_registry("slug-a")
        assert _get_cached_name("slug-a", "model-1") is None
        assert _get_cached_name("slug-a", "model-2") is None
        assert _get_cached_name("slug-b", "model-1") == "cache/b1"

    def test_clear_all(self):
        _store_cached_name("a", "m1", "c1")
        _store_cached_name("b", "m2", "c2")
        clear_cache_registry()
        assert len(_cache_registry) == 0


# ---------------------------------------------------------------------------
# get_or_create_cache
# ---------------------------------------------------------------------------

class TestGetOrCreateCache:
    @pytest.mark.asyncio
    async def test_returns_none_without_api_key(self):
        ctx = _make_ctx()
        with patch.dict("os.environ", {}, clear=True):
            result = await get_or_create_cache(ctx, model="gemini-2.5-flash")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_name_on_hit(self):
        ctx = _make_ctx()
        _store_cached_name("test-biz", "gemini-2.5-flash", "cached/123")

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            result = await get_or_create_cache(ctx, model="gemini-2.5-flash")
            assert result == "cached/123"

    @pytest.mark.asyncio
    async def test_skips_small_context(self):
        ctx = _make_ctx(context_size=100)  # Very small context

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            result = await get_or_create_cache(ctx, model="gemini-2.5-flash", min_tokens=1024)
            assert result is None

    @pytest.mark.asyncio
    async def test_creates_cache_on_miss(self):
        ctx = _make_ctx()
        mock_cache = MagicMock()
        mock_cache.name = "cached/new-456"

        mock_client = MagicMock()
        mock_client.caches.create.return_value = mock_cache

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("backend.lib.gemini_cache.genai") as mock_genai,
        ):
            mock_genai.Client.return_value = mock_client
            result = await get_or_create_cache(ctx, model="gemini-2.5-flash")
            assert result == "cached/new-456"
            assert ctx.gemini_cache_name == "cached/new-456"
            assert _get_cached_name("test-biz", "gemini-2.5-flash") == "cached/new-456"

    @pytest.mark.asyncio
    async def test_returns_none_on_create_failure(self):
        ctx = _make_ctx()
        mock_client = MagicMock()
        mock_client.caches.create.side_effect = Exception("API Error")

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("backend.lib.gemini_cache.genai") as mock_genai,
        ):
            mock_genai.Client.return_value = mock_client
            result = await get_or_create_cache(ctx, model="gemini-2.5-flash")
            assert result is None


# ---------------------------------------------------------------------------
# delete_cache
# ---------------------------------------------------------------------------

class TestDeleteCache:
    @pytest.mark.asyncio
    async def test_deletes_existing_cache(self):
        _store_cached_name("test-biz", "gemini-2.5-flash", "cached/to-delete")
        mock_client = MagicMock()

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("backend.lib.gemini_cache.genai") as mock_genai,
        ):
            mock_genai.Client.return_value = mock_client
            result = await delete_cache("test-biz", "gemini-2.5-flash")
            assert result is True
            assert _get_cached_name("test-biz", "gemini-2.5-flash") is None

    @pytest.mark.asyncio
    async def test_returns_false_for_missing(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            result = await delete_cache("nonexistent", "gemini-2.5-flash")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await delete_cache("test-biz", "gemini-2.5-flash")
            assert result is False
