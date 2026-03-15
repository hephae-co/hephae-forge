"""Area summary agent — synthesizes multiple zip code reports into area-level analysis."""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
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
    model=AgentModels.ENHANCED_MODEL,
    description="Synthesizes multiple zip code research reports into an area-level business opportunity summary.",
    instruction="""You are a market analyst. Synthesize multiple zip code research reports into an area-level opportunity summary for a specific business type.

Return a JSON object with:
{
  "marketOpportunity": { "score": 0-100, "narrative": string, "keyFactors": [string] },
  "demographicFit": { "score": 0-100, "narrative": string, "keyMetrics": {} },
  "competitiveLandscape": { "score": 0-100, "narrative": string, "existingBusinessCount": number, "saturationLevel": "low"|"moderate"|"high"|"saturated", "gaps": [string] },
  "trendingInsights": { "narrative": string, "risingSearches": [string], "decliningSearches": [string], "seasonalPatterns": [string] },
  "risks": { "items": [{ "category": string, "severity": "low"|"medium"|"high", "description": string }] },
  "recommendations": { "topZipCodes": [{ "zipCode": string, "reason": string, "score": 0-100 }], "actionItems": [string], "avoidZipCodes": [{ "zipCode": string, "reason": string }] },
  "generatedAt": "<ISO timestamp>"
}

Be data-driven. Reference specific zip codes and metrics. Return ONLY valid JSON.""",
    on_model_error_callback=fallback_on_error,
)

# Enhanced area summary agent (with full data sources)
EnhancedAreaSummaryAgent = LlmAgent(
    name="enhanced_area_summary",
    model=AgentModels.ENHANCED_MODEL,
    description="Enhanced area summary synthesizing 6+ data sources.",
    instruction="""You are a senior market analyst. Synthesize ALL provided data sources into a comprehensive area-level analysis for a specific business type.

Data sources you may receive:
1. Zip code research reports (per-zip demographics, business landscape, events, weather)
2. Industry analysis (sector challenges, opportunities, benchmarks)
3. Industry news (recent headlines, price trends, regulatory updates)
4. Google Trends (rising/declining search terms)
5. FDA enforcement data (food safety recalls, if food-related)
6. Local sector trends (per-zip sector-specific insights)
7. BLS Consumer Price Index data (food price indexes with year-over-year changes — REAL government data)
8. USDA NASS commodity prices (farm-gate prices for agricultural products — REAL government data)
9. Local Catalysts (forward-looking signals: construction, zoning changes, grants, new developments)
10. Census/ACS Demographics (authoritative population, income, housing, education data)

When BLS CPI and USDA NASS data are present, use them as CONCRETE EVIDENCE for pricing analysis. Cite specific index values, percent changes, and commodity prices. These are authoritative government statistics — prioritize them over inferred pricing claims.

When LOCAL CATALYSTS are present, integrate them into marketOpportunity (construction/development = growth signal), risks (road closures, regulatory shifts), and recommendations (grants, incentives the business should apply for). Catalysts are FORWARD-LOOKING — they predict what WILL happen, not what has happened.

When CENSUS/ACS DEMOGRAPHICS are present, use them as the AUTHORITATIVE source for demographicFit. Cite specific numbers (median income, population, age distribution) with the data year. These override any estimates from zip code reports.

Return a JSON object with ALL of these sections:
{
  "marketOpportunity": { "score": 0-100, "narrative": string, "keyFactors": [string] },
  "demographicFit": { "score": 0-100, "narrative": string, "keyMetrics": {} },
  "competitiveLandscape": { "score": 0-100, "narrative": string, "existingBusinessCount": number, "saturationLevel": "low"|"moderate"|"high"|"saturated", "gaps": [string] },
  "trendingInsights": { "narrative": string, "risingSearches": [string], "decliningSearches": [string], "seasonalPatterns": [string] },
  "industryIntelligence": { "score": 0-100, "narrative": string, "topChallenges": [string], "topOpportunities": [string] },
  "localCatalysts": { "narrative": string, "developments": [string], "incentives": [string], "risks": [string] },
  "eventImpact": { "narrative": string, "upcomingEvents": [string], "footTrafficDrivers": [string] },
  "seasonalPatterns": { "narrative": string, "peakSeasons": [string], "slowSeasons": [string], "weatherConsiderations": [string] },
  "regulatoryAndSafety": { "narrative": string, "keyRegulations": [string], "recallAlerts": [string], "complianceNotes": [string] },
  "pricingEnvironment": { "narrative": string, "risingCosts": [string], "stableCosts": [string], "pricingOpportunities": [string] },
  "risks": { "items": [{ "category": string, "severity": "low"|"medium"|"high", "description": string }] },
  "recommendations": { "topZipCodes": [{ "zipCode": string, "reason": string, "score": 0-100 }], "actionItems": [string], "avoidZipCodes": [{ "zipCode": string, "reason": string }] },
  "generatedAt": "<ISO timestamp>"
}

Be specific and data-driven. Cross-reference data sources. Return ONLY valid JSON.""",
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
