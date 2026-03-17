"""WeeklyPulseAgent — cross-signal analysis engine for zipcode weekly briefings.

Takes aggregated signals (zip research, BLS prices, Google Trends, local news,
local catalysts, Yelp competition, SBA loans, energy costs, crime stats,
education data, weather, legal notices) and produces 3-5 ranked insight cards
with actionable recommendations.

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

You will receive PRE-GATHERED SIGNALS from multiple verified data sources (BLS, FDA, Yelp, SBA, EIA, FBI, NWS, Google Trends, news, government filings). Your job is NOT to report raw facts — the business owner already lives in their community.

## YOUR CORE VALUE: Cross-Signal Analysis

You connect dots across data sources that no individual person could. Every insight MUST cite which specific data sources it draws from.

### ANALYSIS FRAMEWORK (apply in order):

**1. Cross-Signal Correlation** — Find combinations of signals that create opportunities or threats:
- Weather + Events + Day-of-week = foot traffic prediction
- BLS price spike in category X + category Y price drop = substitution opportunity
- New competitor filing (Yelp/SBA/legal notices) + your area's saturation level = competitive threat assessment
- Road closure + event location = parking shift → which businesses gain/lose
- Rising Google search terms + low local supply (Yelp data) = unmet demand signal

**2. Quantified Impact** — ALWAYS include numbers when data supports it:
- "Dairy CPI up 12.1% YoY vs overall food at 3.2% — that's a 8.9pp gap eating your margins"
- "Yelp shows 4 new restaurants in 0.5mi radius in 6 months — saturation increasing"
- "SBA approved 12 new loans in this zip last quarter — 40% above county average"
- "Weekend forecast 72F + 2 outdoor events = expect 25-35% higher foot traffic (based on seasonal patterns)"

**3. Substitution & Menu Engineering** (food businesses):
- When ingredient X is up, recommend specific alternatives that are down or stable
- "Dairy up 12%, poultry DOWN 5.3% → shift weekly special from cream-based to grilled chicken dishes"
- "Eggs up 8% but tofu stable → consider plant-based breakfast option for price-sensitive segment"

**4. Competition Radar**:
- New business filings, liquor license applications, SBA loan approvals in the area
- Yelp new business count, rating changes, price level shifts
- "A new [type] opened 0.3mi away — they're priced at $$ while you're $$$. Consider a lunch special to compete on value."

**5. Economic Context Overlay**:
- Energy costs trend → operating cost pressure
- Free/reduced lunch % (education data) → neighborhood price sensitivity
- Crime stats → safety perception affecting foot traffic
- SBA loan volume → local economic health / new business formation rate

**6. Demand Shift Detection** (Google Trends + Yelp):
- Rising search terms that local businesses could serve
- "Searches for 'outdoor dining' up 40% in your DMA — do you have patio seating?"
- "Searches for 'gluten free near me' rising — consider adding 2-3 GF options"

### WHAT MAKES A WORTHLESS INSIGHT (NEVER do these):
- "It's going to rain Saturday" (they have weather apps)
- "There's a street fair this weekend" (they probably helped organize it)
- "Egg prices are up" (they buy eggs every week and know this)
- Generic advice like "prepare for the weekend" or "check your inventory"
- ANY insight that cites only ONE signal or no specific data
- ANYTHING you are not confident about from the provided data — DO NOT hallucinate facts

### CRITICAL RULE: Only use data you were given
- If a data section is missing or says "empty/skipped", do NOT invent data for it
- EVERY number you cite MUST come from the provided signals
- If you don't have enough data for 3 insights, produce fewer rather than hallucinate
- Mark your confidence: high (multiple corroborating sources), medium (1-2 sources), low (inference)

### OUTPUT RULES:
- Produce 5-8 insight cards, ranked by impactScore (highest first)
- Insights that connect 2+ data sources get higher impactScore (60-100)
- Single-source insights are also valuable — use impactScore 20-59 and impactLevel "low" or "medium"
- Every insight MUST list its data sources in the "dataSources" array (e.g. ["BLS CPI", "Census ACS"])
- Each recommendation must be SPECIFIC and ACTIONABLE (not vague)
- impactScore: 0-100
  - 80-100 (high): Cross-signal correlation backed by 2+ verified data sources
  - 40-79 (medium): Strong single-source signal with clear business relevance
  - 20-39 (low): Noteworthy trend or data point worth monitoring
- timeSensitivity: "this_week" if must act in 7 days, "this_month" if 30 days, "this_quarter" if longer
- headline: One sentence capturing the week's most important theme
- quickStats: Fill ONLY from actual data provided (trending searches, weather, event count, price alerts)

IMPORTANT: Include ALL noteworthy signals as insights, even if they come from a single source.
A BLS price spike is worth reporting even without a second corroborating signal.
A census income datapoint is worth contextualizing even alone.
Use impactLevel to communicate your confidence — don't discard useful information.

Return ONLY the structured JSON matching the schema."""

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

    # ── Zip code research report ─────────────────────────────────────
    if signals.get("zipReport"):
        report = signals["zipReport"]
        sections.append("=== ZIP CODE RESEARCH REPORT ===")
        if isinstance(report, dict):
            for section_name, section_data in report.get("sections", {}).items():
                if section_data:
                    content = section_data if isinstance(section_data, str) else json.dumps(section_data, default=str)
                    sections.append(f"--- {section_name} ---\n{content}")
        sections.append("")

    # ── Weather forecast ─────────────────────────────────────────────
    if signals.get("weather"):
        w = signals["weather"]
        sections.append("=== 7-DAY WEATHER FORECAST (NWS) ===")
        sections.append(f"Summary: {w.get('summary', 'N/A')}")
        sections.append(f"Outdoor favorability: {w.get('outdoorFavorability', 'N/A')}")
        for period in w.get("forecast", [])[:7]:
            sections.append(f"- {period.get('name', '')}: {period.get('temperature', '')}F, {period.get('shortForecast', '')}, precip {period.get('precipChance', 0)}%, wind {period.get('windSpeed', '')}")
        if w.get("alerts"):
            sections.append(f"ALERTS: {json.dumps(w['alerts'], default=str)}")
        sections.append("")

    # ── Census Demographics (BQ — authoritative) ───────────────────
    if signals.get("censusDemographics"):
        c = signals["censusDemographics"]
        sections.append("=== CENSUS DEMOGRAPHICS (ACS 5-Year — verified government data) ===")
        sections.append(f"Population: {c.get('totalPopulation', 'N/A'):,}")
        sections.append(f"Median household income: ${c.get('medianHouseholdIncome', 0):,}")
        sections.append(f"Income per capita: ${c.get('incomePerCapita', 0):,}")
        sections.append(f"Poverty rate: {c.get('povertyRate', 0)}%")
        sections.append(f"Economic stress level: {c.get('economicStressLevel', 'N/A')}")
        sections.append(f"Price sensitivity: {c.get('priceSensitivity', 'N/A')}")
        sections.append(f"Median age: {c.get('medianAge', 'N/A')}")
        sections.append(f"Housing units: {c.get('housingUnits', 0):,} (occupancy {c.get('occupancyRate', 0)}%, vacancy {c.get('vacancyRate', 0)}%)")
        sections.append(f"Median rent: ${c.get('medianRent', 0):,} (rent burden: {c.get('rentBurden', 0)}% of income)")
        sections.append(f"Median home value: ${c.get('medianHomeValue', 0):,}")
        sections.append("")

    # ── OSM Business Density (BQ — real business counts) ─────────
    if signals.get("osmDensity"):
        osm = signals["osmDensity"]
        sections.append("=== BUSINESS DENSITY (OpenStreetMap — real POI data) ===")
        sections.append(f"Total businesses within {osm.get('radiusM', 1500)}m: {osm.get('totalBusinesses', 0)}")
        sections.append(f"Saturation level: {osm.get('saturationLevel', 'N/A')}")
        if osm.get("categories"):
            sections.append(f"Categories: {json.dumps(osm['categories'])}")
        if osm.get("nearby"):
            sections.append("Nearest businesses:")
            for b in osm["nearby"][:5]:
                sections.append(f"  - {b.get('name', '?')} ({b.get('category', '?')}) — {b.get('distanceM', '?')}m")
        sections.append("")

    # ── Historical Weather (NOAA GSOD — 5yr seasonal baseline) ───
    if signals.get("weatherHistory"):
        wh = signals["weatherHistory"]
        sections.append("=== HISTORICAL WEATHER BASELINE (NOAA — 5-year average for this month) ===")
        sections.append(f"Station: {wh.get('station', 'N/A')} ({wh.get('stationDistKm', '?')}km from zip)")
        sections.append(f"Avg temp: {wh.get('avgTempF', 'N/A')}F (high {wh.get('avgHighF', 'N/A')}F, low {wh.get('avgLowF', 'N/A')}F)")
        sections.append(f"Rain days: {wh.get('rainDaysPct', 'N/A')}% of days")
        sections.append(f"Snow days (5yr total): {wh.get('snowDays', 0)}")
        sections.append("USE THIS: Compare the 7-day forecast against these historical averages to flag unusual weather patterns.")
        sections.append("")

    # ── Google Trends ────────────────────────────────────────────────
    if signals.get("trends"):
        trends = signals["trends"]
        sections.append("=== GOOGLE TRENDS (DMA-level) ===")
        sections.append(f"Top terms: {json.dumps(trends.get('topTerms', [])[:15], default=str)}")
        sections.append(f"Rising terms: {json.dumps(trends.get('risingTerms', [])[:15], default=str)}")
        sections.append("")

    # ── BLS CPI price deltas ─────────────────────────────────────────
    if signals.get("priceDeltas"):
        sections.append("=== FOOD/COMMODITY PRICE CHANGES (BLS CPI — verified government data) ===")
        for d in signals["priceDeltas"][:12]:
            yoy = f"YoY: {d['yoyPctChange']:+.1f}%" if d.get("yoyPctChange") is not None else "YoY: N/A"
            mom = f"MoM: {d['momPctChange']:+.2f}%" if d.get("momPctChange") is not None else ""
            sections.append(f"- {d['label']}: {yoy} {mom} (index {d['indexValue']:.1f}, {d['latestPeriod']}) [{d['direction']}]")
        sections.append("")
    elif signals.get("blsCpi"):
        highlights = signals["blsCpi"].get("highlights", [])
        if highlights:
            sections.append("=== BLS CPI HIGHLIGHTS ===")
            sections.append("\n".join(highlights))
            sections.append("")

    # ── USDA commodity prices ────────────────────────────────────────
    if signals.get("usdaPrices"):
        usda = signals["usdaPrices"]
        highlights = usda.get("highlights", [])
        if highlights:
            sections.append("=== USDA COMMODITY PRICES ===")
            sections.append("\n".join(highlights) if isinstance(highlights, list) else json.dumps(highlights, default=str))
            sections.append("")

    # ── FDA recalls ──────────────────────────────────────────────────
    if signals.get("fdaRecalls"):
        fda = signals["fdaRecalls"]
        if fda.get("totalRecalls", 0) > 0:
            sections.append("=== FDA FOOD SAFETY ALERTS ===")
            sections.append(f"Total recalls (1yr): {fda.get('totalRecalls', 0)}, Recent (3mo): {fda.get('recentRecallCount', 0)}")
            sections.append(f"Top reasons: {', '.join(fda.get('topReasons', []))}")
            for e in fda.get("enforcements", [])[:3]:
                sections.append(f"- {e.get('recalling_firm', 'Unknown')}: {e.get('reason_for_recall', '')[:150]} [{e.get('classification', '')}]")
            sections.append("")

    # ── USDA FoodData Central ──────────────────────────────────────
    if signals.get("usdaFoodData"):
        fdc = signals["usdaFoodData"]
        ingredients = fdc.get("ingredients", [])
        if ingredients:
            sections.append("=== USDA FOODDATA CENTRAL (ingredient profiles) ===")
            for ing in ingredients:
                sections.append(f"- {ing.get('ingredient', '')}: {ing.get('description', '')} (cal: {ing.get('calories', 0)}, protein: {ing.get('protein', 0)}g, fat: {ing.get('fat', 0)}g)")
            sections.append("")

    # ── Yelp competition data ────────────────────────────────────────
    if signals.get("yelpData"):
        yelp = signals["yelpData"]
        sections.append("=== YELP COMPETITION DATA (verified business listings) ===")
        sections.append(f"Total businesses in zip: {yelp.get('totalBusinesses', 'N/A')}")
        sections.append(f"Average rating: {yelp.get('avgRating', 'N/A')}")
        sections.append(f"Price distribution: {json.dumps(yelp.get('priceDistribution', {}))}")
        if yelp.get("recentlyOpened"):
            sections.append(f"Recently opened ({len(yelp['recentlyOpened'])}): {json.dumps(yelp['recentlyOpened'][:5], default=str)}")
        if yelp.get("topRated"):
            sections.append(f"Top rated: {json.dumps(yelp['topRated'][:5], default=str)}")
        sections.append("")

    # ── Google Maps competitive landscape ──────────────────────────
    if signals.get("mapsGrounding"):
        mg = signals["mapsGrounding"]
        sections.append("=== GOOGLE MAPS COMPETITIVE LANDSCAPE (Grounding Lite) ===")
        sections.append(f"Total places found: {mg.get('totalPlaces', 'N/A')}")
        sections.append(f"Saturation: {mg.get('saturationAssessment', 'N/A')}")
        if mg.get("categories"):
            sections.append(f"Categories: {json.dumps(mg['categories'])}")
        if mg.get("topPlaces"):
            sections.append("Top competitors:")
            for p in mg["topPlaces"][:5]:
                rating = f"rating {p.get('rating', '?')}" if p.get('rating') else ""
                reviews = f"({p.get('userRatingCount', '?')} reviews)" if p.get('userRatingCount') else ""
                sections.append(f"  - {p.get('name', '?')} {rating} {reviews}")
        if mg.get("summary"):
            sections.append(f"Assessment: {mg['summary']}")
        sections.append("")

    # ── SBA loan data ────────────────────────────────────────────────
    if signals.get("sbaLoans"):
        sba = signals["sbaLoans"]
        sections.append("=== SBA LOAN DATA (business formation signals) ===")
        sections.append(f"Recent loans in zip: {sba.get('recentLoans', 0)}")
        sections.append(f"Total amount: ${sba.get('totalAmount', 0):,.0f}" if sba.get("totalAmount") else "")
        sections.append(f"Avg loan size: ${sba.get('avgLoanSize', 0):,.0f}" if sba.get("avgLoanSize") else "")
        sections.append(f"New business signal: {sba.get('newBusinessSignal', 'N/A')}")
        if sba.get("topIndustries"):
            sections.append(f"Top industries getting loans: {json.dumps(sba['topIndustries'][:5])}")
        sections.append("")

    # ── Energy costs ─────────────────────────────────────────────────
    if signals.get("energyCosts"):
        energy = signals["energyCosts"]
        sections.append("=== ENERGY COSTS (EIA — state-level operating cost signal) ===")
        sections.append(f"Commercial electricity: {energy.get('latestPrice', 'N/A')} cents/kWh")
        if energy.get("yoyChange") is not None:
            sections.append(f"Year-over-year change: {energy['yoyChange']:+.1f}% [{energy.get('trend', '')}]")
        sections.append("")

    # ── Crime/safety data ────────────────────────────────────────────
    if signals.get("crimeStats"):
        crime = signals["crimeStats"]
        sections.append("=== CRIME / SAFETY (FBI UCR — county-level) ===")
        sections.append(f"Safety level: {crime.get('safetyLevel', 'N/A')}")
        if crime.get("violentCrimeRate"):
            sections.append(f"Violent crime rate: {crime['violentCrimeRate']} per 100k")
        if crime.get("propertyCrimeRate"):
            sections.append(f"Property crime rate: {crime['propertyCrimeRate']} per 100k")
        sections.append(f"Trend: {crime.get('trend', 'N/A')}")
        sections.append("")

    # ── Education/economic stress ────────────────────────────────────
    if signals.get("educationData"):
        edu = signals["educationData"]
        sections.append("=== EDUCATION / ECONOMIC STRESS PROXY (SchoolDigger) ===")
        sections.append(f"Schools in area: {edu.get('schoolCount', 'N/A')}")
        sections.append(f"Free/reduced lunch %: {edu.get('freeReducedLunchPct', 'N/A')}% — economic stress level: {edu.get('economicStressLevel', 'N/A')}")
        sections.append(f"Family friendliness: {edu.get('familyFriendliness', 'N/A')}")
        sections.append("")

    # ── Legal notices / government filings ───────────────────────────
    if signals.get("legalNotices"):
        legal = signals["legalNotices"]
        sections.append("=== LEGAL NOTICES / GOVERNMENT FILINGS ===")
        sections.append(f"New business filings: {legal.get('newBusinessFilings', 0)}")
        sections.append(f"Zoning changes: {legal.get('zoningChanges', 0)}")
        for notice in legal.get("notices", [])[:5]:
            sections.append(f"- [{notice.get('type', '')}] {notice.get('description', '')} ({notice.get('date', '')})")
        sections.append("")

    # ── Social / Community Pulse ────────────────────────────────────
    if signals.get("socialPulse"):
        sp = signals["socialPulse"]
        sections.append("=== COMMUNITY PULSE (Reddit, X, Patch, TapInto — search grounded) ===")
        sections.append(sp.get("summary", ""))
        sections.append("")

    # ── Local news ───────────────────────────────────────────────────
    if signals.get("localNews"):
        articles = signals["localNews"].get("articles", [])
        if articles:
            sections.append("=== LOCAL NEWS (Google News RSS) ===")
            for article in articles[:8]:
                sections.append(f"- [{article.get('publishedDate', '')}] {article.get('headline', '')} ({article.get('source', '')})")
                if article.get("summary"):
                    sections.append(f"  {article['summary'][:200]}")
            sections.append("")

    # ── Local government catalysts ───────────────────────────────────
    if signals.get("localCatalysts"):
        catalysts = signals["localCatalysts"]
        if isinstance(catalysts, dict):
            sections.append("=== LOCAL GOVERNMENT CATALYSTS (planning boards, DPW, grants) ===")
            sections.append(f"Summary: {catalysts.get('summary', '')}")
            for cat in catalysts.get("catalysts", []):
                sections.append(f"- [{cat.get('type', '')}] {cat.get('signal', '')} (timing: {cat.get('timing', '')}, confidence: {cat.get('confidence', '')})")
            if catalysts.get("recommendation"):
                sections.append(f"Analyst note: {catalysts['recommendation']}")
            sections.append("")

    # ── Prior week's pulse (delta detection) ─────────────────────────
    if prior_pulse:
        sections.append("=== PRIOR WEEK'S BRIEFING (compare for deltas) ===")
        prior = prior_pulse.get("pulse", prior_pulse)
        sections.append(f"Headline: {prior.get('headline', 'N/A')}")
        for insight in prior.get("insights", [])[:3]:
            sections.append(f"- [{insight.get('rank', '')}] {insight.get('title', '')}: {insight.get('analysis', '')[:150]}")
        sections.append("")

    # ── Data availability summary ────────────────────────────────────
    available = [k for k in signals.keys() if signals[k]]
    sections.append(f"=== DATA SOURCES AVAILABLE: {', '.join(available)} ===")
    sections.append("IMPORTANT: Only cite data from the sources listed above. If a source is missing, say so — do NOT invent data.")

    return "\n".join(sections)


async def generate_weekly_pulse(
    zip_code: str,
    business_type: str,
    week_of: str,
    signals: dict[str, Any],
    prior_pulse: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the WeeklyPulseAgent to generate a weekly briefing."""
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

    output.setdefault("zipCode", zip_code)
    output.setdefault("businessType", business_type)
    output.setdefault("weekOf", week_of)

    logger.info(f"[WeeklyPulse] Generated {len(output.get('insights', []))} insights")
    return output
