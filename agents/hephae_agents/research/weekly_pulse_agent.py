"""WeeklyPulseAgent — cross-signal analysis engine for zipcode weekly briefings.

Takes aggregated signals (zip research, BLS prices, Google Trends, local news,
local catalysts, industry data) and produces 3-5 ranked insight cards with
actionable recommendations.

The agent does NOT gather data — it ANALYZES pre-gathered signals and finds
cross-correlations, anomalies, and opportunities that a business owner wouldn't
spot on their own.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas import WeeklyPulseOutput

logger = logging.getLogger(__name__)

WEEKLY_PULSE_INSTRUCTION = """You are a Senior Local Business Intelligence Analyst producing a weekly briefing for a specific business type in a specific zip code.

You will receive PRE-GATHERED SIGNALS from multiple data sources. Your job is NOT to report raw facts — the business owner already lives in their community and knows basic things like weather and local events.

Your job is to perform CROSS-SIGNAL ANALYSIS and produce insights the owner CANNOT derive on their own:

### What makes a VALUABLE insight:
1. **Cross-Signal Correlation**: Connect dots between unrelated data. "Street fair + 72F + Saturday = historically higher foot traffic 5-8pm. But road closure on Oak St shifts parking east."
2. **Quantified Impact**: Don't say "prepare for busy weekend". Say "expect 25-35% higher traffic Saturday evening based on similar past events."
3. **Things They Don't Know**: Competitor permit filings, zoning changes, search trend spikes, supply chain recalls, BLS price movements vs overall inflation.
4. **Industry-Specific Actionable Recs**: Not "food prices are up" but "Dairy up 12% while poultry DOWN 5% — shift weekly special from cream-based to grilled chicken."
5. **Anomaly Detection**: What's different this week vs typical? What broke the pattern?

### What makes a WORTHLESS insight (NEVER do these):
- "It's going to rain Saturday" (they have weather apps)
- "There's a street fair this weekend" (they probably helped organize it)
- "Egg prices are up" (they buy eggs every week and know this)
- Generic advice like "prepare for the weekend" or "check your inventory"

### Analysis Tasks:
1. Cross-correlate signals: What combinations create opportunities or threats?
2. Quantify impact: Based on available data, estimate magnitude.
3. Detect anomalies: What's unusual compared to baseline?
4. Generate recommendations: What should a business owner of this type DO?
5. Prioritize: Rank by actionability and time-sensitivity.

### Output Rules:
- Produce exactly 3-5 insight cards, ranked by impactScore (highest first)
- Each insight must connect at least 2 different signals
- Each recommendation must be SPECIFIC and ACTIONABLE (not vague)
- impactScore: 0-100 (80+ = high, 40-79 = medium, <40 = low)
- timeSensitivity: "this_week" if must act in 7 days, "this_month" if 30 days, "this_quarter" if longer
- headline: One sentence that captures the week's most important theme
- quickStats: Fill from available data (trending searches, weather, event count, price alert count)

Return ONLY the structured JSON matching the schema. No markdown fencing."""

WeeklyPulseAgent = LlmAgent(
    name="weekly_pulse",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Analyzes cross-signal data to produce weekly insight cards for local businesses.",
    instruction=WEEKLY_PULSE_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)


def _build_signal_prompt(
    zip_code: str,
    business_type: str,
    week_of: str,
    signals: dict[str, Any],
    prior_pulse: dict[str, Any] | None = None,
) -> str:
    """Build the prompt with all gathered signal data for the agent."""
    sections: list[str] = [
        f"ZIP CODE: {zip_code}",
        f"BUSINESS TYPE: {business_type}",
        f"WEEK OF: {week_of}",
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    # Zip code research report (demographics, events, weather, business landscape)
    if signals.get("zipReport"):
        report = signals["zipReport"]
        sections.append("=== ZIP CODE RESEARCH REPORT ===")
        if isinstance(report, dict):
            for section_name, section_data in report.get("sections", {}).items():
                if section_data:
                    content = section_data if isinstance(section_data, str) else json.dumps(section_data, default=str)
                    sections.append(f"--- {section_name} ---\n{content}")
        sections.append("")

    # Google Trends
    if signals.get("trends"):
        trends = signals["trends"]
        sections.append("=== GOOGLE TRENDS (DMA-level) ===")
        sections.append(json.dumps(trends, default=str))
        sections.append("")

    # BLS CPI price data with deltas
    if signals.get("priceDeltas"):
        sections.append("=== FOOD/COMMODITY PRICE DELTAS (BLS CPI) ===")
        sections.append(json.dumps(signals["priceDeltas"], default=str))
        sections.append("")
    elif signals.get("blsCpi"):
        sections.append("=== BLS CPI DATA ===")
        # Just send highlights to keep prompt focused
        highlights = signals["blsCpi"].get("highlights", [])
        sections.append("\n".join(highlights) if highlights else "No highlights available")
        sections.append("")

    # USDA prices
    if signals.get("usdaPrices"):
        sections.append("=== USDA COMMODITY PRICES ===")
        usda = signals["usdaPrices"]
        sections.append(json.dumps(usda.get("highlights", []), default=str))
        sections.append("")

    # FDA recalls
    if signals.get("fdaRecalls"):
        sections.append("=== FDA FOOD SAFETY ALERTS ===")
        fda = signals["fdaRecalls"]
        sections.append(f"Total recalls (1yr): {fda.get('totalRecalls', 0)}")
        sections.append(f"Recent (3mo): {fda.get('recentRecallCount', 0)}")
        sections.append(f"Top reasons: {json.dumps(fda.get('topReasons', []))}")
        # Include most recent enforcements
        enforcements = fda.get("enforcements", [])[:5]
        if enforcements:
            sections.append("Recent enforcements:")
            sections.append(json.dumps(enforcements, default=str))
        sections.append("")

    # Local news
    if signals.get("localNews"):
        sections.append("=== LOCAL NEWS ===")
        articles = signals["localNews"].get("articles", [])
        for article in articles[:8]:
            sections.append(f"- [{article.get('publishedDate', '')}] {article.get('headline', '')} ({article.get('source', '')})")
            if article.get("summary"):
                sections.append(f"  {article['summary'][:200]}")
        sections.append("")

    # Local catalysts (government signals)
    if signals.get("localCatalysts"):
        sections.append("=== LOCAL GOVERNMENT CATALYSTS ===")
        catalysts = signals["localCatalysts"]
        if isinstance(catalysts, dict):
            sections.append(f"Summary: {catalysts.get('summary', '')}")
            for cat in catalysts.get("catalysts", []):
                sections.append(f"- [{cat.get('type', '')}] {cat.get('signal', '')} (timing: {cat.get('timing', '')}, confidence: {cat.get('confidence', '')})")
        sections.append("")

    # Industry news
    if signals.get("industryNews"):
        sections.append("=== INDUSTRY NEWS ===")
        news = signals["industryNews"]
        if isinstance(news, dict):
            for item in news.get("recentNews", [])[:5]:
                sections.append(f"- {item.get('headline', '')}: {item.get('summary', '')}")
            for trend in news.get("priceTrends", []):
                sections.append(f"- Price: {trend.get('item', '')} is {trend.get('trend', '')} — {trend.get('detail', '')}")
        sections.append("")

    # Prior week's pulse (for delta detection)
    if prior_pulse:
        sections.append("=== PRIOR WEEK'S BRIEFING (for comparison) ===")
        prior = prior_pulse.get("pulse", prior_pulse)
        sections.append(f"Headline: {prior.get('headline', 'N/A')}")
        for insight in prior.get("insights", [])[:3]:
            sections.append(f"- [{insight.get('rank', '')}] {insight.get('title', '')}: {insight.get('analysis', '')[:150]}")
        sections.append("")

    return "\n".join(sections)


async def generate_weekly_pulse(
    zip_code: str,
    business_type: str,
    week_of: str,
    signals: dict[str, Any],
    prior_pulse: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the WeeklyPulseAgent to generate a weekly briefing.

    Args:
        zip_code: Target zip code.
        business_type: Business category (e.g. "Restaurants").
        week_of: ISO date for the week (YYYY-MM-DD).
        signals: Dict of pre-gathered signal data.
        prior_pulse: Previous week's pulse for delta detection (optional).

    Returns:
        WeeklyPulseOutput as a dict.
    """
    logger.info(f"[WeeklyPulse] Generating pulse for {zip_code} / {business_type} / {week_of}")

    prompt = _build_signal_prompt(zip_code, business_type, week_of, signals, prior_pulse)

    result = await run_agent_to_json(
        WeeklyPulseAgent,
        prompt,
        app_name="weekly_pulse",
        response_schema=WeeklyPulseOutput,
    )

    if result and isinstance(result, WeeklyPulseOutput):
        output = result.model_dump()
    elif result and isinstance(result, dict):
        output = result
    else:
        logger.warning("[WeeklyPulse] Agent returned empty result — generating fallback")
        output = {
            "zipCode": zip_code,
            "businessType": business_type,
            "weekOf": week_of,
            "headline": "Insufficient data to generate pulse this week.",
            "insights": [],
            "quickStats": {},
        }

    # Ensure required fields are populated
    output.setdefault("zipCode", zip_code)
    output.setdefault("businessType", business_type)
    output.setdefault("weekOf", week_of)

    logger.info(f"[WeeklyPulse] Generated {len(output.get('insights', []))} insights")
    return output
