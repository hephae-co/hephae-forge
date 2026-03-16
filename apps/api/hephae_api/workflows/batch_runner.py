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


def build_traffic_synthesis_prompt(deferred: dict[str, Any]) -> str:
    """Build the traffic synthesis prompt from deferred intel data.

    Args:
        deferred: The deferred dict from ForecasterAgent with intel + identity.

    Returns:
        The full synthesis prompt string.
    """
    from datetime import datetime as _dt

    intel = deferred.get("intel", {})
    identity = deferred.get("identity", {})
    admin_context = deferred.get("business_context_summary", "No additional admin research data available.")

    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    coords = identity.get("coordinates") or {}
    lat = coords.get("lat", 0)
    lng = coords.get("lng", 0)

    today = _dt.now()
    date_string = today.strftime("%A, %B %d, %Y")

    return f"""
      **CURRENT DATE**: {date_string}

      Your task is to generate exactly a 3-day foot traffic forecast based STRICTLY on the gathered intelligence below for {name}. Never return more than 3 days in the array.

      ### 1. BUSINESS INTELLIGENCE
      {intel.get("poi", "No POI data found.")}

      ### 2. WEATHER INTELLIGENCE
      {intel.get("weather", "No weather data found.")}

      ### 3. EVENT INTELLIGENCE
      {intel.get("events", "No events data found.")}

      ### 4. ADMIN RESEARCH CONTEXT (if available)
      {admin_context}

      **ANALYSIS RULES** (MUST follow in order):
      1. **HOURS**: If the business is CLOSED, Traffic Level MUST be "Closed".
      2. **WEATHER — CHECK BOTH SOURCES**: Read Section 2 (real-time weather) AND Section 4 (admin research context, especially "Seasonal Weather" or "seasonal_weather"). If EITHER source mentions storms, severe weather, temperature drops, or hazardous conditions for ANY forecast day, you MUST reflect that in the weatherNote AND reduce traffic scores for that day. Do NOT write "Standard seasonal conditions" if severe weather is documented in any source.
      3. **EVENTS & DISTANCE**: Major nearby events boost traffic scores significantly.

      **OUTPUT**:
      Return ONLY valid JSON matching this structure perfectly. Do not include markdown ```json blocks.
      Keep all text fields SHORT — bullet-style, no paragraphs.
      {{
        "business": {{
          "name": "{name}",
          "address": "{address}",
          "coordinates": {{ "lat": {lat}, "lng": {lng} }},
          "type": "String",
          "nearbyPOIs": [
              {{ "name": "String", "type": "String" }}
          ]
        }},
        "summary": "One crisp sentence, max 20 words.",
        "forecast": [
          {{
            "date": "YYYY-MM-DD",
            "dayOfWeek": "String",
            "localEvents": ["Short event name"],
            "weatherNote": "5-8 words max",
            "slots": [
               {{ "label": "Morning", "score": 0, "level": "Low/Medium/High/Closed", "reason": "5-10 words max" }},
               {{ "label": "Lunch", "score": 0, "level": "Low/Medium/High/Closed", "reason": "5-10 words max" }},
               {{ "label": "Afternoon", "score": 0, "level": "Low/Medium/High/Closed", "reason": "5-10 words max" }},
               {{ "label": "Evening", "score": 0, "level": "Low/Medium/High/Closed", "reason": "5-10 words max" }}
            ]
          }}
        ]
      }}
    """


def build_competitive_positioning_prompt(deferred: dict[str, Any]) -> str:
    """Build the market positioning prompt from deferred profiler data.

    Args:
        deferred: The deferred dict from run_competitive_analysis with competitorBrief + identity.

    Returns:
        The full positioning prompt string.
    """
    import json as _json
    from hephae_agents.competitive_analysis.prompts import MARKET_POSITIONING_INSTRUCTION

    identity = deferred.get("identity", {})
    brief = deferred.get("competitorBrief", "")
    context_data = deferred.get("contextData", "")

    parts = [MARKET_POSITIONING_INSTRUCTION]
    if identity:
        parts.append(f"\n\nTARGET RESTAURANT: {_json.dumps(identity)}")
    if brief:
        parts.append(f"\n\nCOMPETITORS BRIEF:\n{brief}")
    if context_data:
        parts.append(f"\n\n{context_data}")
    parts.append("\n\nGenerate the final competitive json report.")

    return "\n".join(parts)


async def run_synthesis_batch(
    items: list[dict[str, Any]],
    timeout_seconds: int = 300,
) -> dict[str, dict] | None:
    """Batch traffic synthesis + competitive positioning prompts.

    Args:
        items: List of {"request_id": str, "prompt": str}.

    Returns:
        Dict mapping request_id -> parsed JSON result, or None.
    """
    return await run_batch(items, timeout_seconds)
