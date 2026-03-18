"""Gemini Batch API — submit multiple prompts at reduced cost.

Two modes:
  1. Inline batch — collect prompts, submit via genai batches API (50% cost reduction)
  2. Vertex AI batch — for very large batches (100+), uses GCS + Vertex AI jobs

For workflow usage, prefer inline batch (simpler, faster startup).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


async def batch_generate(
    prompts: list[dict[str, Any]],
    model: str = "",
    config: dict | None = None,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Submit multiple prompts as individual async calls with concurrency control.

    Uses the standard Gemini API but with controlled concurrency to avoid
    rate limits. For true batch pricing, use submit_vertex_batch().

    Set BATCH_DISABLED=true to run sequentially one-at-a-time (debug mode).

    Args:
        prompts: List of {"request_id": str, "prompt": str}.
        model: Model ID (defaults to PRIMARY_MODEL).
        config: Optional GenerateContentConfig dict.
        timeout_seconds: Max total time.

    Returns:
        Dict mapping request_id -> parsed JSON response (or {"raw_text": ...}).
    """
    from hephae_common.gemini_client import get_genai_client
    from hephae_common.model_config import AgentModels

    if not prompts:
        return {}

    # Debug bypass — run sequentially, one at a time
    if os.environ.get("BATCH_DISABLED", "").lower() == "true":
        logger.info(f"[GeminiBatch] BATCH_DISABLED=true, running {len(prompts)} prompts sequentially")
        client = get_genai_client()
        _model = model or AgentModels.PRIMARY_MODEL
        results: dict[str, Any] = {}
        for item in prompts:
            request_id = item["request_id"]
            try:
                gen_config = config or {"response_mime_type": "application/json"}
                response = await client.aio.models.generate_content(
                    model=_model,
                    contents=item["prompt"],
                    config=gen_config,
                )
                text = response.text
                try:
                    results[request_id] = json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    results[request_id] = {"raw_text": text}
            except Exception as e:
                logger.warning(f"[GeminiBatch] Sequential call failed for {request_id}: {e}")
                results[request_id] = None
        return results

    model = model or AgentModels.PRIMARY_MODEL
    client = get_genai_client()

    results: dict[str, Any] = {}
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent calls

    async def _call(item: dict):
        request_id = item["request_id"]
        prompt_text = item["prompt"]
        async with semaphore:
            try:
                gen_config = config or {"response_mime_type": "application/json"}
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt_text,
                    config=gen_config,
                )
                text = response.text
                try:
                    results[request_id] = json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    results[request_id] = {"raw_text": text}
            except Exception as e:
                logger.warning(f"[GeminiBatch] Failed for {request_id}: {e}")
                results[request_id] = None

    try:
        await asyncio.wait_for(
            asyncio.gather(*[_call(p) for p in prompts], return_exceptions=True),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[GeminiBatch] Timeout after {timeout_seconds}s, {len(results)}/{len(prompts)} completed")

    logger.info(f"[GeminiBatch] Completed {len(results)}/{len(prompts)} requests")
    return results


async def submit_vertex_batch(
    requests: list[dict[str, Any]],
    model: str = "",
    gcs_bucket: str = "",
    timeout_seconds: int = 300,
) -> dict[str, Any] | None:
    """Submit a batch inference job to Vertex AI Batch Prediction API.

    Best for large batches (100+). For smaller batches, use batch_generate().

    Args:
        requests: List of dicts with keys: request_id, contents, config (optional).
        model: Gemini model ID.
        gcs_bucket: GCS bucket for JSONL input/output.
        timeout_seconds: Max time to wait before falling back.

    Returns:
        Dict mapping request_id -> parsed response, or None on failure/timeout.
    """
    import uuid

    if not requests:
        return {}

    from hephae_common.model_config import AgentModels
    model = model or AgentModels.PRIMARY_MODEL

    gcs_bucket = gcs_bucket or os.environ.get("BATCH_EVAL_GCS_BUCKET", "hephae-batch-evaluations")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")

    if not project_id:
        logger.warning("[VertexBatch] No GOOGLE_CLOUD_PROJECT set, skipping batch")
        return None

    try:
        from google.cloud import storage
        from google.cloud import aiplatform
    except ImportError:
        logger.warning("[VertexBatch] google-cloud-aiplatform not installed, skipping batch")
        return None

    batch_id = f"hephae-batch-{uuid.uuid4().hex[:8]}"
    gcs_input_path = f"gs://{gcs_bucket}/batch-inputs/{batch_id}.jsonl"

    # Build JSONL
    jsonl_lines = []
    for req in requests:
        line = {
            "request_id": req["request_id"],
            "model": f"publishers/google/models/{model}",
            "contents": req["contents"],
        }
        if req.get("config"):
            line["generation_config"] = req["config"]
        if req.get("tools"):
            line["tools"] = req["tools"]
        jsonl_lines.append(json.dumps(line))

    jsonl_content = "\n".join(jsonl_lines)

    # Upload to GCS
    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(f"batch-inputs/{batch_id}.jsonl")
        blob.upload_from_string(jsonl_content, content_type="application/jsonl")
        logger.info(f"[VertexBatch] Uploaded {len(requests)} requests to {gcs_input_path}")
    except Exception as e:
        logger.error(f"[VertexBatch] Failed to upload JSONL: {e}")
        return None

    # Submit batch job
    gcs_output_prefix = f"gs://{gcs_bucket}/batch-outputs/{batch_id}/"
    try:
        aiplatform.init(project=project_id, location=location)
        batch_job = aiplatform.BatchPredictionJob.create(
            job_display_name=batch_id,
            model_name=f"publishers/google/models/{model}",
            gcs_source=gcs_input_path,
            gcs_destination_prefix=gcs_output_prefix,
            sync=False,
        )
        logger.info(f"[VertexBatch] Submitted batch job: {batch_job.resource_name}")
    except Exception as e:
        logger.error(f"[VertexBatch] Failed to submit batch job: {e}")
        return None

    # Poll for completion
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        await asyncio.sleep(10)
        try:
            batch_job.refresh()
            state = batch_job.state.name if batch_job.state else "UNKNOWN"
            if state == "JOB_STATE_SUCCEEDED":
                logger.info(f"[VertexBatch] Job completed in {time.monotonic() - start:.0f}s")
                break
            elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
                logger.error(f"[VertexBatch] Job {state}: {batch_job.error}")
                return None
        except Exception as e:
            logger.warning(f"[VertexBatch] Poll error: {e}")
    else:
        logger.warning(f"[VertexBatch] Timeout after {timeout_seconds}s")
        return None

    # Parse output
    try:
        output_blobs = list(bucket.list_blobs(prefix=f"batch-outputs/{batch_id}/"))
        results: dict[str, Any] = {}
        for blob in output_blobs:
            if not blob.name.endswith(".jsonl"):
                continue
            content = blob.download_as_text()
            for line in content.strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                req_id = entry.get("request_id", "")
                response = entry.get("response", {})
                candidates = response.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                    try:
                        results[req_id] = json.loads(text)
                    except (json.JSONDecodeError, ValueError):
                        results[req_id] = {"raw_text": text}
                else:
                    results[req_id] = None

        logger.info(f"[VertexBatch] Parsed {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"[VertexBatch] Failed to parse output: {e}")
        return None
