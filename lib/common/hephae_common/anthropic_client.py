"""Anthropic Claude API client — async wrapper for dual-model synthesis.

Uses the Anthropic messages API directly via httpx. The API key is read
from the ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


async def generate_claude(
    prompt: str,
    system: str = "",
    model: str = "",
    max_tokens: int = MAX_TOKENS,
    response_format: str = "json",
) -> dict[str, Any] | str | None:
    """Call Claude via the Anthropic messages API.

    Args:
        prompt: User message text.
        system: System prompt.
        model: Model ID (defaults to Claude Sonnet 4).
        max_tokens: Max response tokens.
        response_format: "json" to parse as JSON, "text" for raw text.

    Returns:
        Parsed JSON dict, raw text string, or None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[Claude] No ANTHROPIC_API_KEY set — skipping Claude synthesis")
        return None

    model = model or DEFAULT_MODEL

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=body)

            if resp.status_code != 200:
                logger.error(f"[Claude] API returned {resp.status_code}: {resp.text[:500]}")
                return None

            data = resp.json()
            content_blocks = data.get("content", [])
            text = "".join(
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            )

            if not text:
                logger.warning("[Claude] Empty response")
                return None

            if response_format == "json":
                # Strip markdown fences if present
                clean = text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
                try:
                    return json.loads(clean)
                except json.JSONDecodeError:
                    logger.warning(f"[Claude] Failed to parse JSON, returning raw text")
                    return {"raw_text": text}

            return text

    except httpx.TimeoutException:
        logger.error(f"[Claude] Request timed out after 120s")
        return None
    except Exception as e:
        logger.error(f"[Claude] Request failed: {e}")
        return None
