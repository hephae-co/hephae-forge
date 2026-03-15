"""Area summary agent — synthesizes multiple zip code reports into area-level analysis."""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import AreaSummaryOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


def _condense_reports(reports: list[dict]) -> list[dict]:
    """Reduce token usage by ~70% — extract only summary + key_facts per section."""
    condensed = []
    for report in reports:
        entry = {
            "zip_code": report.get("zip_code", ""),
            "summary": report.get("summary", ""),
        }
        sections = report.get("sections", {})
        entry["sections"] = {}
        for key, section in sections.items():
            if isinstance(section, dict):
                entry["sections"][key] = {
                    "summary": (section.get("content", "") or "")[:200],
                    "key_facts": section.get("key_facts", []),
                }
        condensed.append(entry)
    return condensed


# Basic area summary agent
AreaSummaryAgent = LlmAgent(
    name="area_summary",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Synthesizes multiple zip code research reports into an area-level business opportunity summary.",
    instruction="""You are a market analyst. Synthesize zip code reports into an area-level opportunity summary.

Return JSON. Keep ALL narrative fields to 1-2 sentences max. Use bullet-style phrases, not paragraphs.
{
  "marketOpportunity": { "score": 0-100, "narrative": "1 sentence", "keyFactors": ["short phrase each"] },
  "demographicFit": { "score": 0-100, "narrative": "1 sentence", "keyMetrics": {} },
  "competitiveLandscape": { "score": 0-100, "narrative": "1 sentence", "existingBusinessCount": number, "saturationLevel": "low"|"moderate"|"high"|"saturated", "gaps": ["short phrase"] },
  "trendingInsights": { "narrative": "1 sentence", "risingSearches": [string], "decliningSearches": [string], "seasonalPatterns": [string] },
  "risks": { "items": [{ "category": string, "severity": "low"|"medium"|"high", "description": "1 sentence" }] },
  "recommendations": { "topZipCodes": [{ "zipCode": string, "reason": "1 sentence", "score": 0-100 }], "actionItems": ["short phrase"], "avoidZipCodes": [{ "zipCode": string, "reason": "1 sentence" }] },
  "generatedAt": "<ISO timestamp>"
}

Be data-driven. Reference specific zip codes and numbers. Return ONLY valid JSON.""",
    on_model_error_callback=fallback_on_error,
)

# Enhanced area summary agent (with full data sources)
EnhancedAreaSummaryAgent = LlmAgent(
    name="enhanced_area_summary",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Enhanced area summary synthesizing 6+ data sources.",
    instruction="""You are a senior market analyst. Synthesize ALL provided data sources into a concise area-level analysis.

Data sources: zip code reports, industry analysis, news, Google Trends, FDA data, BLS CPI, USDA prices, local catalysts, Census demographics. Use whichever are provided.

Rules:
- BLS/USDA data = CONCRETE EVIDENCE — cite specific numbers
- Census/ACS = AUTHORITATIVE demographics — cite with data year
- Local catalysts = FORWARD-LOOKING signals
- ALL narrative fields: 1-2 sentences max. Use bullet phrases in arrays, not paragraphs.

Return JSON with sections: marketOpportunity, demographicFit, competitiveLandscape, trendingInsights, industryIntelligence, localCatalysts, eventImpact, seasonalPatterns, regulatoryAndSafety, pricingEnvironment, risks, recommendations, generatedAt.

Each section: { "score": 0-100, "narrative": "1-2 sentences", ...arrays of short phrases }.
recommendations: { "topZipCodes": [{ "zipCode", "reason": "1 sentence", "score" }], "actionItems": ["short phrase"], "avoidZipCodes": [{ "zipCode", "reason": "1 sentence" }] }

Return ONLY valid JSON.""",
    on_model_error_callback=fallback_on_error,
)


async def generate_area_summary(
    business_type: str,
    reports: list[dict],
) -> dict:
    """Generate a basic area summary from zip code reports."""
    condensed = _condense_reports(reports)
    prompt = f"BUSINESS TYPE: {business_type}\n\nZIP CODE REPORTS:\n{json.dumps(condensed)}"

    result = await run_agent_to_json(
        AreaSummaryAgent, prompt, app_name="area_summary", response_schema=AreaSummaryOutput
    )
    if not result or not isinstance(result, AreaSummaryOutput):
        raise ValueError("Failed to generate area summary")
    return result.model_dump()


async def generate_enhanced_area_summary(
    business_type: str,
    reports: list[dict],
    industry_analysis: dict | None = None,
    industry_news: dict | None = None,
    trends_data: dict | None = None,
    fda_data: dict | None = None,
    local_sector_trends: list[dict] | None = None,
    bls_cpi_data: dict | None = None,
    usda_price_data: dict | None = None,
    local_catalysts: dict | None = None,
    demographic_data: dict | None = None,
) -> dict:
    """Generate an enhanced area summary with all data sources."""
    condensed = _condense_reports(reports)

    sections = [f"BUSINESS TYPE: {business_type}", f"ZIP CODE REPORTS:\n{json.dumps(condensed)}"]

    if industry_analysis:
        sections.append(f"INDUSTRY ANALYSIS:\n{json.dumps(industry_analysis)}")
    if industry_news:
        sections.append(f"INDUSTRY NEWS:\n{json.dumps(industry_news)}")
    if trends_data:
        sections.append(f"GOOGLE TRENDS:\n{json.dumps(trends_data)}")
    if fda_data:
        sections.append(f"FDA ENFORCEMENT DATA:\n{json.dumps(fda_data)}")
    if local_sector_trends:
        sections.append(f"LOCAL SECTOR TRENDS:\n{json.dumps(local_sector_trends)}")
    if bls_cpi_data:
        sections.append(f"BLS CONSUMER PRICE INDEX (food prices):\n{json.dumps(bls_cpi_data)}")
    if usda_price_data:
        sections.append(f"USDA NASS COMMODITY PRICES (farm-gate prices):\n{json.dumps(usda_price_data)}")
    if local_catalysts:
        sections.append(f"LOCAL CATALYSTS (forward-looking signals):\n{json.dumps(local_catalysts)}")
    if demographic_data:
        sections.append(f"CENSUS/ACS DEMOGRAPHICS (authoritative):\n{json.dumps(demographic_data)}")

    prompt = "\n\n".join(sections)

    result = await run_agent_to_json(
        EnhancedAreaSummaryAgent, prompt, app_name="enhanced_area_summary", response_schema=AreaSummaryOutput
    )
    if not result or not isinstance(result, AreaSummaryOutput):
        raise ValueError("Failed to generate enhanced area summary")
    return result.model_dump()
