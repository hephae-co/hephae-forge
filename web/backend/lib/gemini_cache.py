"""
Gemini context caching — creates and manages server-side cached content.

Uses the Gemini API caching feature to avoid re-sending large business context
to every agent call. Cache is model-specific with a 1-hour TTL.

Usage:
    from backend.lib.gemini_cache import get_or_create_cache

    cache_name = await get_or_create_cache(ctx, model="gemini-2.5-flash")
    # Pass cache_name to agent via session state or before_model_callback
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from google import genai
from google.genai.types import CreateCachedContentConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache name registry (slug+model → cache_name, with TTL)
# ---------------------------------------------------------------------------

_CACHE_TTL_S = 3500  # slightly less than server-side TTL (3600s) to avoid stale refs
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_or_create_cache(
    business_context: Any,
    model: str,
    min_tokens: int = 1024,
) -> Optional[str]:
    """Get or create a Gemini cached content for the given BusinessContext.

    Args:
        business_context: A BusinessContext instance with to_prompt_context().
        model: The Gemini model name (cache is model-specific).
        min_tokens: Minimum estimated tokens to justify caching. Skip if context is too small.

    Returns:
        The cache name string, or None if caching was skipped or failed.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[GeminiCache] No GEMINI_API_KEY — skipping cache creation")
        return None

    slug = getattr(business_context, "slug", "unknown")

    # Check local registry first
    existing = _get_cached_name(slug, model)
    if existing:
        logger.info(f"[GeminiCache] Reusing existing cache for {slug} on {model}")
        return existing

    # Build the context text
    try:
        context_text = business_context.to_prompt_context()
    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to serialize context for {slug}: {e}")
        return None

    # Skip if context is too small (Gemini caching has a minimum token requirement)
    estimated_tokens = len(context_text) // 4
    if estimated_tokens < min_tokens:
        logger.info(
            f"[GeminiCache] Context too small for {slug} (~{estimated_tokens} tokens < {min_tokens}). Skipping cache."
        )
        return None

    # Create the cache
    try:
        client = genai.Client(api_key=api_key)
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

        # Store on the context object
        business_context.gemini_cache_name = cache_name

        return cache_name

    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to create cache for {slug} on {model}: {e}")
        return None


async def delete_cache(slug: str, model: str) -> bool:
    """Delete a cached content entry.

    Returns True if deleted successfully, False otherwise.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return False

    cache_name = _get_cached_name(slug, model)
    if not cache_name:
        return False

    try:
        client = genai.Client(api_key=api_key)
        client.caches.delete(name=cache_name)
        _cache_registry.pop(_cache_key(slug, model), None)
        logger.info(f"[GeminiCache] Deleted cache for {slug}: {cache_name}")
        return True
    except Exception as e:
        logger.warning(f"[GeminiCache] Failed to delete cache {cache_name}: {e}")
        return False


def clear_cache_registry(slug: str | None = None) -> None:
    """Clear local cache registry. If slug is None, clear all."""
    if slug:
        keys = [k for k in _cache_registry if k.startswith(f"{slug}:")]
        for k in keys:
            _cache_registry.pop(k, None)
    else:
        _cache_registry.clear()
