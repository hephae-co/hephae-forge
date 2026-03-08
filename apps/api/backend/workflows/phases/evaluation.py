"""Evaluation phase — runs QA evaluators on completed capabilities."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.firestore.businesses import get_business
from backend.types import BusinessWorkflowState, BusinessPhase, EvaluationResult
from backend.workflows.capabilities.registry import get_evaluable_capabilities

logger = logging.getLogger(__name__)


async def run_evaluation_phase(
    businesses: list[BusinessWorkflowState],
    callbacks: dict[str, Callable],
) -> None:
    """Evaluate completed capabilities for each business."""
    pending = [b for b in businesses if b.phase in (BusinessPhase.ANALYSIS_DONE, BusinessPhase.EVALUATING)]
    evaluable = get_evaluable_capabilities()

    for biz in pending:
        biz.phase = BusinessPhase.EVALUATING

        try:
            biz_data = await get_business(biz.slug)
            latest_outputs = (biz_data or {}).get("latestOutputs", {})
            identity = (biz_data or {}).get("identity", {"name": biz.name, "address": biz.address})

            for cap_def in evaluable:
                if cap_def.name not in biz.capabilitiesCompleted:
                    continue
                if cap_def.firestore_output_key not in latest_outputs:
                    continue
                if not cap_def.evaluator:
                    continue

                agent = cap_def.evaluator.agent_factory()
                prompt = cap_def.evaluator.build_prompt(
                    identity,
                    latest_outputs[cap_def.firestore_output_key],
                    {"officialUrl": biz.officialUrl, **identity},
                )

                result = await run_agent_to_json(agent, prompt, app_name=cap_def.evaluator.app_name)

                if result and isinstance(result, dict):
                    biz.evaluations[cap_def.name] = EvaluationResult(
                        score=result.get("score", 0),
                        isHallucinated=result.get("isHallucinated", True),
                        issues=result.get("issues", []),
                    )
                else:
                    biz.evaluations[cap_def.name] = EvaluationResult(
                        score=0, isHallucinated=True, issues=["Failed to parse evaluator output"]
                    )

            eval_results = [v for v in biz.evaluations.values() if v]
            biz.qualityPassed = (
                len(eval_results) > 0
                and all(e.score >= 80 and not e.isHallucinated for e in eval_results)
            )

            biz.phase = BusinessPhase.EVALUATION_DONE
        except Exception as e:
            logger.error(f"[Evaluation] Error evaluating {biz.slug}: {e}")
            biz.lastError = str(e)
            biz.phase = BusinessPhase.EVALUATION_DONE
            biz.qualityPassed = False

        if callbacks.get("onBusinessEvaluated"):
            await callbacks["onBusinessEvaluated"](biz.slug, biz.qualityPassed)
