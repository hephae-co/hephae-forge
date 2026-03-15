"""Insights agent — synthesizes cross-capability findings for a business."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.firestore.businesses import get_business
from hephae_db.schemas import InsightsOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

InsightsAgent = LlmAgent(
    name="insights_agent",
    model=AgentModels.PRIMARY_MODEL,
    description="Synthesizes cross-capability findings into actionable insights for a business.",
    instruction="""You are a business intelligence synthesizer. Given multiple capability outputs (SEO, traffic, competitive, margin analysis) for a specific business, generate concise, actionable insights.

Return a JSON object with:
{
  "summary": string (2-3 sentences — the big picture),
  "keyFindings": [string] (3-5 most important findings across all capabilities),
  "recommendations": [string] (3-5 specific, prioritized action items)
}

Be specific — reference actual data from the capability outputs.
When the business data includes a FOOD_PRICING_CONTEXT section, incorporate cost environment
analysis into your recommendations. Reference specific BLS/USDA data points (e.g., "dairy up
3.2% YoY per BLS CPI") when suggesting menu strategy, pricing adjustments, or margin optimization.
Distinguish between rising-cost categories (where margins are under pressure) and stable/declining
categories (where there may be pricing opportunities).
Return ONLY valid JSON. No markdown fencing.""",
    on_model_error_callback=fallback_on_error,
)


async def generate_insights(business_slug: str) -> dict | None:
    """Generate insights for a business from its latest capability outputs.

    Fetches business data from Firestore, generates insights, and persists them.
    Returns the insights dict or None on failure.
    """
    try:
        biz = await get_business(business_slug)
        if not biz:
            logger.warning(f"[Insights] Business {business_slug} not found")
            return None

        outputs = biz.get("latestOutputs", {})
        if not outputs:
            logger.warning(f"[Insights] No capability outputs for {business_slug}")
            return None

        identity = {
            "name": biz.get("name", ""),
            "address": biz.get("address", ""),
        }

        prompt = f"BUSINESS: {json.dumps(identity)}\n\nCAPABILITY OUTPUTS:\n{json.dumps(outputs)}"

        food_ctx = biz.get("foodPricingContext") or biz.get("identity", {}).get("foodPricingContext")
        if food_ctx:
            prompt += f"\n\nFOOD_PRICING_CONTEXT:\n{json.dumps(food_ctx)}"

        result = await run_agent_to_json(InsightsAgent, prompt, app_name="insights", response_schema=InsightsOutput)

        if result and isinstance(result, InsightsOutput):
            result_dict = result.model_dump()
            result_dict["generatedAt"] = datetime.utcnow().isoformat()

            # Persist insights to Firestore
            from hephae_common.firebase import get_db
            db = get_db()
            await asyncio.to_thread(
                db.collection("businesses").document(business_slug).update,
                {"insights": result_dict},
            )

            logger.info(f"[Insights] Generated and saved insights for {business_slug}")
            return result_dict

        return None
    except Exception as e:
        logger.error(f"[Insights] Failed for {business_slug}: {e}")
        return None


def build_insights_prompt(biz: dict) -> str | None:
    """Build an insights prompt for batch submission. Returns None if no data."""
    outputs = biz.get("latestOutputs", {})
    if not outputs:
        return None

    identity = {"name": biz.get("name", ""), "address": biz.get("address", "")}
    prompt = f"BUSINESS: {json.dumps(identity)}\n\nCAPABILITY OUTPUTS:\n{json.dumps(outputs)}"

    food_ctx = biz.get("foodPricingContext") or biz.get("identity", {}).get("foodPricingContext")
    if food_ctx:
        prompt += f"\n\nFOOD_PRICING_CONTEXT:\n{json.dumps(food_ctx)}"

    prompt += (
        "\n\nReturn JSON: {\"summary\": \"2-3 sentences\", "
        "\"keyFindings\": [\"3-5 findings\"], "
        "\"recommendations\": [\"3-5 action items\"]}"
    )
    return prompt


async def generate_insights_batch(slugs: list[str]) -> dict[str, dict | None]:
    """Generate insights for multiple businesses via batched Gemini calls.

    Returns dict mapping slug -> insights dict (or None on failure).
    """
    from hephae_db.firestore.businesses import get_business
    from hephae_common.gemini_batch import batch_generate

    # Build prompts
    prompts = []
    for slug in slugs:
        try:
            biz = await get_business(slug)
            if not biz:
                continue
            prompt = build_insights_prompt(biz)
            if prompt:
                prompts.append({"request_id": slug, "prompt": prompt})
        except Exception as e:
            logger.warning(f"[Insights] Failed to build prompt for {slug}: {e}")

    if not prompts:
        return {}

    logger.info(f"[Insights] Submitting batch of {len(prompts)} insights prompts")
    batch_results = await batch_generate(prompts=prompts, timeout_seconds=180)

    # Persist results
    results: dict[str, dict | None] = {}
    for slug in slugs:
        raw = batch_results.get(slug) if batch_results else None
        if raw and isinstance(raw, dict) and "summary" in raw:
            raw["generatedAt"] = datetime.utcnow().isoformat()
            try:
                from hephae_common.firebase import get_db
                db = get_db()
                await asyncio.to_thread(
                    db.collection("businesses").document(slug).update,
                    {"insights": raw},
                )
            except Exception as e:
                logger.warning(f"[Insights] Firestore persist failed for {slug}: {e}")
            results[slug] = raw
            logger.info(f"[Insights] Batch-generated insights for {slug}")
        else:
            results[slug] = None

    return results
