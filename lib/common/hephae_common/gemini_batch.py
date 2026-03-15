"""Vertex AI Batch Prediction wrapper for bulk inference.

Formats requests as JSONL, uploads to GCS, submits batch job via Vertex AI,
polls until complete or timeout, returns parsed results keyed by request_id.
On failure/timeout returns None (caller falls back to sequential).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def submit_batch_inference(
    requests: list[dict[str, Any]],
    model: str = "gemini-3.1-flash-lite-preview",
    gcs_bucket: str = "",
    timeout_seconds: int = 300,
) -> dict[str, Any] | None:
    """Submit a batch inference job to Vertex AI and poll until complete.

    Args:
        requests: List of dicts with keys: request_id, contents, config (optional).
        model: Gemini model ID.
        gcs_bucket: GCS bucket for JSONL input/output.
        timeout_seconds: Max time to wait before falling back.

    Returns:
        Dict mapping request_id -> parsed response, or None on failure/timeout.
    """
    if not requests:
        return {}

    gcs_bucket = gcs_bucket or os.environ.get("BATCH_EVAL_GCS_BUCKET", "hephae-batch-evaluations")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")

    if not project_id:
        logger.warning("[GeminiBatch] No GOOGLE_CLOUD_PROJECT set, skipping batch")
        return None

    try:
        from google.cloud import storage
        from google.cloud import aiplatform
    except ImportError:
        logger.warning("[GeminiBatch] google-cloud-aiplatform not installed, skipping batch")
        return None

    batch_id = f"hephae-eval-{uuid.uuid4().hex[:8]}"
    gcs_input_path = f"gs://{gcs_bucket}/batch-inputs/{batch_id}.jsonl"
    gcs_output_prefix = f"gs://{gcs_bucket}/batch-outputs/{batch_id}/"

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
        jsonl_lines.append(json.dumps(line))

    jsonl_content = "\n".join(jsonl_lines)

    # Upload to GCS
    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(f"batch-inputs/{batch_id}.jsonl")
        blob.upload_from_string(jsonl_content, content_type="application/jsonl")
        logger.info(f"[GeminiBatch] Uploaded {len(requests)} requests to {gcs_input_path}")
    except Exception as e:
        logger.error(f"[GeminiBatch] Failed to upload JSONL: {e}")
        return None

    # Submit batch job
    try:
        aiplatform.init(project=project_id, location=location)

        batch_job = aiplatform.BatchPredictionJob.create(
            job_display_name=batch_id,
            model_name=f"publishers/google/models/{model}",
            gcs_source=gcs_input_path,
            gcs_destination_prefix=gcs_output_prefix,
            sync=False,
        )
        logger.info(f"[GeminiBatch] Submitted batch job: {batch_job.resource_name}")
    except Exception as e:
        logger.error(f"[GeminiBatch] Failed to submit batch job: {e}")
        return None

    # Poll for completion
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        await asyncio.sleep(10)
        try:
            batch_job.refresh()
            state = batch_job.state.name if batch_job.state else "UNKNOWN"
            if state == "JOB_STATE_SUCCEEDED":
                logger.info(f"[GeminiBatch] Job completed in {time.monotonic() - start:.0f}s")
                break
            elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
                logger.error(f"[GeminiBatch] Job {state}: {batch_job.error}")
                return None
        except Exception as e:
            logger.warning(f"[GeminiBatch] Poll error: {e}")
    else:
        logger.warning(f"[GeminiBatch] Timeout after {timeout_seconds}s, falling back to sequential")
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
                # Extract text from Vertex AI batch response format
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

        logger.info(f"[GeminiBatch] Parsed {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"[GeminiBatch] Failed to parse output: {e}")
        return None
