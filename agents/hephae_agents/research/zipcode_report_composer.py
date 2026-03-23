"""Zip code report composer — transforms raw findings into structured report."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import ZipcodeReportComposerOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

ReportComposerAgent = LlmAgent(
    name="zipcode_report_composer",
    model=AgentModels.PRIMARY_MODEL,
    description="Transforms raw research findings and trends data into a structured zip code report.",
    instruction="""You are a report composer. Transform the raw research findings and Google Trends data into a clean, structured JSON report.

Produce a JSON object with this exact structure:
{
    "summary": "A 2-3 sentence executive summary of this zip code",
    "zip_code": "<the zip code>",
    "sections": {
        "geography": { "title": "Geography & Location", "content": "...", "key_facts": ["..."] },
        "demographics": { "title": "Demographics", "content": "...", "key_facts": ["..."] },
        "census_housing": { "title": "Census & Housing", "content": "...", "key_facts": ["..."] },
        "business_landscape": { "title": "Local Business Landscape", "content": "...", "key_facts": ["..."] },
        "economic_indicators": { "title": "Economic Indicators", "content": "...", "key_facts": ["..."] },
        "consumer_market": { "title": "Consumer Behavior & Market Gaps", "content": "...", "key_facts": ["..."] },
        "infrastructure": { "title": "Infrastructure & Amenities", "content": "...", "key_facts": ["..."] },
        "trending": { "title": "Google Trends & Search Interest", "content": "...", "key_facts": ["..."] },
        "events": { "title": "Upcoming Local Events (Next 2 Weeks)", "content": "...", "key_facts": ["..."] },
        "seasonal_weather": { "title": "Current Weather & Near-Term Forecast", "content": "...", "key_facts": ["..."] }
    },
    "source_count": <number>
}

Each section MUST have at least 3 key_facts. The content field should be 2-4 sentences minimum.
The "events" and "seasonal_weather" sections are optional — include them if the research findings contain relevant data.""",
    on_model_error_callback=fallback_on_error,
)


async def compose_zipcode_report(
    zip_code: str,
    findings: str,
    trends_data: dict | None = None,
) -> dict:
    """Compose a structured ZipCodeReport from raw research findings and trends data."""
    trends_section = ""
    if trends_data:
        top = trends_data.get("topTerms", [])
        rising = trends_data.get("risingTerms", [])
        if top or rising:
            trends_section = f"\n\nGOOGLE TRENDS DATA:\nTop Terms: {json.dumps(top)}\nRising Terms: {json.dumps(rising)}"
    if not trends_section:
        trends_section = "\n\nGOOGLE TRENDS DATA: No trends data available for this region."

    prompt = f"ZIP CODE: {zip_code}\n\nRESEARCH FINDINGS:\n{findings}{trends_section}"

    parsed = await run_agent_to_json(
        ReportComposerAgent, prompt, app_name="zipcode_report_composer", response_schema=ZipcodeReportComposerOutput
    )

    if not parsed or not isinstance(parsed, ZipcodeReportComposerOutput):
        raise ValueError("Failed to compose report — agent returned invalid output")

    # Convert to dict and ensure all required fields are set
    result = parsed.model_dump()
    result["zip_code"] = zip_code
    result.setdefault("researched_at", datetime.utcnow().isoformat())

    return result
