"""Batch orchestrator — collects prompts and submits them as batched Gemini calls.

Supports batching for:
  - Qualification classifier (N businesses → 1 batch)
  - Evaluation agents (N businesses × M capabilities → 1 batch)
  - Insights generation (N businesses → 1 batch)
  - Traffic synthesis (N businesses → 1 batch)
"""

from __future__ import annotations

import logging
from typing import Any

from hephae_common.gemini_batch import batch_generate

logger = logging.getLogger(__name__)

# Below this count, sequential is fine (batch overhead not worth it)
MIN_BATCH_SIZE = 3


async def run_batch(
    items: list[dict[str, Any]],
    timeout_seconds: int = 300,
) -> dict[str, Any] | None:
    """Submit a list of prompts as a batch.

    Args:
        items: List of {"request_id": str, "prompt": str, ...}.
        timeout_seconds: Max wait time.

    Returns:
        Dict mapping request_id -> parsed result, or None to fall back.
    """
    if len(items) < MIN_BATCH_SIZE:
        logger.info(f"[BatchRunner] Only {len(items)} items, below threshold — skipping batch")
        return None

    prompts = [
        {"request_id": item["request_id"], "prompt": item["prompt"]}
        for item in items
    ]

    return await batch_generate(
        prompts=prompts,
        timeout_seconds=timeout_seconds,
    )


async def run_evaluations_batch(
    eval_items: list[dict[str, Any]],
    timeout_seconds: int = 300,
    gcs_bucket: str = "",
) -> dict[str, dict] | None:
    """Submit all evaluation prompts as a batch."""
    return await run_batch(eval_items, timeout_seconds)


async def run_qualification_batch(
    businesses: list[dict[str, Any]],
    timeout_seconds: int = 120,
) -> dict[str, dict] | None:
    """Batch-classify businesses as HVT or not.

    Args:
        businesses: List of {"slug": str, "prompt": str} where prompt is the
                    classification prompt built by the scanner.

    Returns:
        Dict mapping slug -> {"is_hvt": bool, "reason": str}, or None.
    """
    items = [
        {"request_id": biz["slug"], "prompt": biz["prompt"]}
        for biz in businesses
    ]
    return await run_batch(items, timeout_seconds)


async def run_insights_batch(
    items: list[dict[str, Any]],
    timeout_seconds: int = 180,
) -> dict[str, dict] | None:
    """Batch-generate insights for multiple businesses.

    Args:
        items: List of {"request_id": slug, "prompt": str}.

    Returns:
        Dict mapping slug -> insights dict, or None.
    """
    return await run_batch(items, timeout_seconds)
