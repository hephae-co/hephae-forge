"""Gemini context caching — creates and manages server-side cached content."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from google.genai.types import CreateCachedContentConfig
from hephae_common.gemini_client import get_genai_client

logger = logging.getLogger(__name__)

_CACHE_TTL_S = 3500
_cache_registry: dict[str, tuple[str, float]] = {}


def _cache_key(slug: str, model: str) -> str:
    return f"{slug}:{model}"


def _get_cached_name(slug: str, model: str) -> Optional[str]:
    key = _cache_key(slug, model)
    entry = _cache_registry.get(key)
    if entry and (time.time() - entry[1]) < _CACHE_TTL_S:
        return entry[0]
    _cache_registry.pop(key, None)
    return None


def _store_cached_name(slug: str, model: str, cache_name: str) -> None:
    _cache_registry[_cache_key(slug, model)] = (cache_name, time.time())


async def get_or_create_cache(
    business_context: Any,
    model: str,
    min_tokens: int = 1024,
) -> Optional[str]:
    """Get or create a Gemini cached content for the given BusinessContext."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    slug = getattr(business_context, "slug", "unknown")

    existing = _get_cached_name(slug, model)
    if existing:
        logger.info(f"[GeminiCache] Reusing existing cache for {slug} on {model}")
        return existing

    try:
        context_text = business_context.to_prompt_context()
    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to serialize context for {slug}: {e}")
        return None

    estimated_tokens = len(context_text) // 4
    if estimated_tokens < min_tokens:
        return None

    try:
        client = get_genai_client()
        cache = client.caches.create(
            model=model,
            config=CreateCachedContentConfig(
                display_name=f"hephae-{slug}",
                system_instruction="Complete business context for analysis. Use this data to ground your responses with real local market data, demographics, and competitive intelligence.",
                contents=[context_text],
                ttl="3600s",
            ),
        )

        cache_name = cache.name
        _store_cached_name(slug, model, cache_name)
        logger.info(f"[GeminiCache] Created cache for {slug} on {model}: {cache_name}")
        business_context.gemini_cache_name = cache_name
        return cache_name
    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to create cache for {slug} on {model}: {e}")
        return None


async def delete_cache(slug: str, model: str) -> bool:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return False

    cache_name = _get_cached_name(slug, model)
    if not cache_name:
        return False

    try:
        client = get_genai_client()
        client.caches.delete(name=cache_name)
        _cache_registry.pop(_cache_key(slug, model), None)
        return True
    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to delete cache {cache_name}: {e}")
        return False


def clear_cache_registry(slug: str | None = None) -> None:
    if slug:
        keys = [k for k in _cache_registry if k.startswith(f"{slug}:")]
        for k in keys:
            _cache_registry.pop(k, None)
    else:
        _cache_registry.clear()
