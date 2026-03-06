"""
LLM-as-Judge — uses Gemini Flash to score discovery results for "realness".

Each field in the enriched profile gets a score from 1-5:
  1 = clearly hallucinated / fabricated
  2 = suspicious, likely wrong
  3 = plausible but unverifiable
  4 = likely correct, matches known facts
  5 = verified correct

The judge receives both the enriched profile AND the ground-truth TestBusiness
facts, so it can cross-reference.
"""

from __future__ import annotations

import json
import logging
import os

from google import genai
from google.genai import types

from backend.config import AgentModels
from backend.tests.integration.businesses import GroundTruth

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """\
You are a fact-checking judge for a business discovery system.

You will receive:
1. A discovered business profile (JSON)
2. Known ground-truth facts about the business

Score EACH of the following fields on a 1-5 scale:
- name (does it match the real business name?)
- officialUrl (is this the real website?)
- address (is this the real address for this business?)
- phone (is this a real phone number for this business?)
- socialLinks (are these real social media profiles?)
- primaryColor (does it look like a real brand color, not random?)
- persona (does the persona match the business type?)
- competitors (are these real competing businesses in the area?)
- socialProfileMetrics (are the social media metrics plausible?)

Scoring guide:
  1 = clearly hallucinated or fabricated (wrong business, made-up URL)
  2 = suspicious, likely wrong (URL exists but wrong business)
  3 = plausible but cannot verify (generic/reasonable but unconfirmed)
  4 = likely correct (matches known facts closely)
  5 = verified correct (exact match with ground truth)

For socialProfileMetrics specifically:
  - Score 1 if follower counts are absurdly high (>10M for a local business) or negative
  - Score 2 if platform URLs in metrics don't match the socialLinks URLs
  - Score 3 if metrics exist and are within plausible ranges
  - Score 4-5 if metrics match known social presence patterns for this business type
  - If socialProfileMetrics is null/missing but business has known social platforms, score 2
  - If Yelp rating exists, it must be between 1.0 and 5.0
  - If overallPresenceScore exists, it must be between 0 and 100

Return ONLY a JSON object with this structure:
{
  "scores": {
    "name": <1-5>,
    "officialUrl": <1-5>,
    "address": <1-5>,
    "phone": <1-5>,
    "socialLinks": <1-5>,
    "primaryColor": <1-5>,
    "persona": <1-5>,
    "competitors": <1-5>,
    "socialProfileMetrics": <1-5>
  },
  "overall": <float, average of all scores>,
  "flags": ["<field>: <reason>", ...]
}

Be strict. If a field is null/missing, score it 1. If a URL looks fabricated, score it 1-2.
"""


async def evaluate_discovery(
    profile: dict,
    ground_truth: GroundTruth,
) -> dict:
    """Run LLM-as-judge on a discovery result. Returns scores dict."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY required for LLM judge")

    client = genai.Client(api_key=api_key)

    facts = (
        f"Business: {ground_truth.name}\n"
        f"Type: {ground_truth.biz_type}\n"
        f"City: {ground_truth.city}, {ground_truth.state}\n"
        f"Expected URL fragment: {ground_truth.expected_url_fragment}\n"
        f"Expected name fragment: {ground_truth.expected_name_fragment}\n"
        f"Known social platforms: {', '.join(ground_truth.expected_social_platforms)}\n"
        f"Is restaurant: {ground_truth.is_restaurant}\n"
    )

    # Strip any binary data before sending to judge
    safe_profile = {k: v for k, v in profile.items() if k != "menuScreenshotBase64"}

    content = (
        f"{JUDGE_PROMPT}\n\n"
        f"--- DISCOVERED PROFILE ---\n{json.dumps(safe_profile, indent=2, default=str)}\n\n"
        f"--- GROUND TRUTH ---\n{facts}"
    )

    response = await client.aio.models.generate_content(
        model=AgentModels.DEFAULT_FAST_MODEL,
        contents=content,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, ValueError):
        logger.error(f"[LLMJudge] Failed to parse response: {response.text}")
        raise ValueError("LLM judge returned unparseable response")

    # Ensure overall is computed
    scores = result.get("scores", {})
    if scores:
        result["overall"] = sum(scores.values()) / len(scores)

    return result
