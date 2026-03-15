"""Batch evaluation orchestrator — submits evaluations as a Vertex AI batch job.

Two functions:
  - run_evaluations_batch() — collects all eval prompts, submits as one batch
  - run_capabilities_batch() — for tool-free capabilities (traffic, competitive)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from hephae_common.model_config import AgentModels
from hephae_common.gemini_batch import submit_batch_inference

logger = logging.getLogger(__name__)

# Below this count, sequential is faster than batch overhead
MIN_BATCH_SIZE = 8


async def run_evaluations_batch(
    eval_items: list[dict[str, Any]],
    timeout_seconds: int = 300,
    gcs_bucket: str = "",
) -> dict[str, dict] | None:
    """Submit all evaluation prompts as a single batch job.

    Args:
        eval_items: List of dicts with keys: request_id, prompt, capability_name.
        timeout_seconds: Max wait time before falling back to sequential.
        gcs_bucket: GCS bucket for batch I/O.

    Returns:
        Dict mapping request_id -> parsed eval result, or None to fall back.
    """
    if len(eval_items) < MIN_BATCH_SIZE:
        logger.info(f"[BatchRunner] Only {len(eval_items)} items, below threshold {MIN_BATCH_SIZE} — skipping batch")
        return None

    requests = []
    for item in eval_items:
        requests.append({
            "request_id": item["request_id"],
            "contents": [{"role": "user", "parts": [{"text": item["prompt"]}]}],
            "config": {"response_mime_type": "application/json"},
        })

    return await submit_batch_inference(
        requests=requests,
        model=AgentModels.PRIMARY_MODEL,
        gcs_bucket=gcs_bucket,
        timeout_seconds=timeout_seconds,
    )


async def run_capabilities_batch(
    cap_items: list[dict[str, Any]],
    timeout_seconds: int = 300,
    gcs_bucket: str = "",
) -> dict[str, dict] | None:
    """Submit tool-free capability prompts as a batch job.

    Only suitable for capabilities that don't use tools (traffic, competitive).

    Args:
        cap_items: List of dicts with keys: request_id, prompt, capability_name.
        timeout_seconds: Max wait time.
        gcs_bucket: GCS bucket.

    Returns:
        Dict mapping request_id -> parsed result, or None to fall back.
    """
    if len(cap_items) < MIN_BATCH_SIZE:
        return None

    requests = []
    for item in cap_items:
        requests.append({
            "request_id": item["request_id"],
            "contents": [{"role": "user", "parts": [{"text": item["prompt"]}]}],
            "config": {"response_mime_type": "application/json"},
        })

    return await submit_batch_inference(
        requests=requests,
        model=AgentModels.PRIMARY_MODEL,
        gcs_bucket=gcs_bucket,
        timeout_seconds=timeout_seconds,
    )
