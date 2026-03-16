"""Evaluation phase — runs QA evaluators on completed capabilities.

Supports two modes:
  1. Batch: collects all eval prompts and submits via Vertex AI batch API (if enabled)
  2. Sequential: runs each evaluator one at a time (fallback or debug mode)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable

from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.firestore.businesses import get_business
from hephae_db.bigquery.feedback import record_evaluation_feedback
from hephae_api.types import BusinessWorkflowState, BusinessPhase, EvaluationResult
from hephae_api.workflows.capabilities.registry import get_evaluable_capabilities

logger = logging.getLogger(__name__)


def _is_batch_enabled() -> bool:
    """Check if batch evaluation is enabled (production Cloud Run only)."""
    return os.environ.get("BATCH_EVAL_ENABLED", "true").lower() == "true"


async def run_evaluation_phase(
    businesses: list[BusinessWorkflowState],
    callbacks: dict[str, Callable],
    debug: bool = False,
) -> None:
    """Evaluate completed capabilities for each business."""
    pending = [b for b in businesses if b.phase in (BusinessPhase.ANALYSIS_DONE, BusinessPhase.EVALUATING)]
    evaluable = get_evaluable_capabilities()

    # Collect all eval items across businesses for potential batching
    eval_items: list[dict] = []
    for biz in pending:
        biz.phase = BusinessPhase.EVALUATING
        try:
            biz_data = await get_business(biz.slug)
            latest_outputs = (biz_data or {}).get("latestOutputs", {})
            identity = (biz_data or {}).get("identity", {"name": biz.name, "address": biz.address})

            for cap_def in evaluable:
                # Check actual business doc outputs (not workflow capabilitiesCompleted
                # which may be stale due to Cloud Tasks polling sync gap)
                if cap_def.firestore_output_key not in latest_outputs:
                    continue
                if not cap_def.evaluator:
                    continue

                cap_output = latest_outputs[cap_def.firestore_output_key]
                if cap_def.eval_compressor and isinstance(cap_output, dict):
                    cap_output = cap_def.eval_compressor(cap_output)
                prompt = cap_def.evaluator.build_prompt(
                    identity,
                    cap_output,
                    {"officialUrl": biz.officialUrl, **identity},
                )
                eval_items.append({
                    "request_id": f"{biz.slug}:{cap_def.name}",
                    "prompt": prompt,
                    "capability_name": cap_def.name,
                    "biz": biz,
                    "cap_def": cap_def,
                    "latest_outputs": latest_outputs,
                })
        except Exception as e:
            logger.error(f"[Evaluation] Error preparing evals for {biz.slug}: {e}")
            biz.lastError = str(e)
            biz.phase = BusinessPhase.EVALUATION_DONE
            biz.qualityPassed = False
            if callbacks.get("onBusinessEvaluated"):
                await callbacks["onBusinessEvaluated"](biz.slug, biz.qualityPassed)

    # Finalize any pending businesses that had zero evaluable outputs
    eval_biz_slugs = {item["biz"].slug for item in eval_items}
    for biz in pending:
        if biz.slug not in eval_biz_slugs:
            biz.phase = BusinessPhase.EVALUATION_DONE
            biz.qualityPassed = False
            logger.info(f"[Evaluation] {biz.slug}: no evaluable outputs — marked evaluation_done (failed)")
            if callbacks.get("onBusinessEvaluated"):
                await callbacks["onBusinessEvaluated"](biz.slug, biz.qualityPassed)

    if not eval_items:
        return

    # Try batch mode first (if enabled and not debug)
    batch_results = None
    if _is_batch_enabled() and not debug:
        try:
            from hephae_api.workflows.batch_runner import run_evaluations_batch
            from hephae_api.config import settings
            batch_results = await run_evaluations_batch(
                eval_items,
                timeout_seconds=settings.BATCH_EVAL_FALLBACK_TIMEOUT,
                gcs_bucket=settings.BATCH_EVAL_GCS_BUCKET,
            )
        except Exception as e:
            logger.warning(f"[Evaluation] Batch submission failed, falling back to sequential: {e}")

    # Process results (batch or sequential fallback)
    for item in eval_items:
        biz = item["biz"]
        cap_def = item["cap_def"]
        result = None

        if batch_results and item["request_id"] in batch_results:
            result = batch_results[item["request_id"]]
        else:
            # Sequential fallback
            try:
                agent = cap_def.evaluator.agent_factory()
                result = await run_agent_to_json(agent, item["prompt"], app_name=cap_def.evaluator.app_name)
            except Exception as e:
                logger.error(f"[Evaluation] Sequential eval failed for {biz.slug}/{cap_def.name}: {e}")

        if result and isinstance(result, dict):
            # Coerce score to float — evaluators sometimes return strings like "85/100"
            raw_score = result.get("score", 0)
            try:
                score = float(raw_score) if not isinstance(raw_score, (int, float)) else raw_score
            except (ValueError, TypeError):
                logger.warning(f"[Evaluation] Non-numeric score from {cap_def.name} for {biz.slug}: {raw_score!r}")
                score = 0
            eval_result = EvaluationResult(
                score=score,
                isHallucinated=result.get("isHallucinated", True),
                issues=result.get("issues", []),
            )
        else:
            eval_result = EvaluationResult(
                score=0, isHallucinated=True, issues=["Failed to parse evaluator output"]
            )

        biz.evaluations[cap_def.name] = eval_result

        # Record evaluation feedback to BigQuery (fire-and-forget)
        asyncio.create_task(record_evaluation_feedback(
            business_slug=biz.slug,
            capability=cap_def.name,
            agent_name=cap_def.firestore_output_key,
            agent_version=item["latest_outputs"].get(cap_def.firestore_output_key, {}).get("agentVersion", ""),
            eval_score=eval_result.score,
            is_hallucinated=eval_result.isHallucinated,
            zip_code=biz.sourceZipCode or "",
            business_type=biz.businessType or "",
        ))

    # Finalize phase for each business
    biz_set = {item["biz"].slug: item["biz"] for item in eval_items}
    for biz in biz_set.values():
        eval_results = [v for v in biz.evaluations.values() if v]
        biz.qualityPassed = (
            len(eval_results) > 0
            and all(e.score >= 80 and not e.isHallucinated for e in eval_results)
        )
        biz.phase = BusinessPhase.EVALUATION_DONE

        if callbacks.get("onBusinessEvaluated"):
            await callbacks["onBusinessEvaluated"](biz.slug, biz.qualityPassed)
