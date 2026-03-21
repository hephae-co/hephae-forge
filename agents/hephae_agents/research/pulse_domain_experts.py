"""Stage 2: PreSynthesis — domain expert agents that distill raw signals.

Three LlmAgents run in parallel, each reading from session.state and
writing a focused report to their output_key:

  PreSynthesis (ParallelAgent)
  ├─ PulseHistorySummarizer → "trendNarrative"
  ├─ EconomistAgent         → "macroReport"
  └─ LocalScoutAgent        → "localReport"

These focused reports replace the 15+ raw JSON blocks that the synthesis
agent previously had to process, reducing "lost in the middle" attention
dilution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from google.adk.agents import LlmAgent, ParallelAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic instruction builders — read from session.state
# ---------------------------------------------------------------------------


def _historian_instruction(ctx) -> str:
    state = getattr(ctx, "state", {})
    zip_code = state.get("zipCode", "")
    business_type = state.get("businessType", "")
    history_insights = state.get("pulseHistoryInsights", [])

    # Format last 12 weeks of insights for trend detection
    history_text = ""
    if history_insights:
        for i, week_insights in enumerate(history_insights[:12]):
            if isinstance(week_insights, list):
                titles = [ins.get("title", "") for ins in week_insights if isinstance(ins, dict)]
                history_text += f"Week -{i+1}: {'; '.join(titles)}\n"
            elif isinstance(week_insights, str):
                history_text += f"Week -{i+1}: {week_insights[:200]}\n"

    return f"""You are a Trend Historian for {business_type} businesses in zip code {zip_code}.

Analyze the last 12 weeks of pulse insights to identify:
1. **Recurring themes** — topics that appear in 3+ weeks
2. **Escalating trends** — signals that are getting stronger week over week
3. **Resolved issues** — problems from past weeks that are no longer present
4. **Seasonal patterns** — signals that align with time-of-year expectations
5. **New anomalies** — signals THIS week that have never appeared before

PULSE HISTORY (most recent first):
{history_text or "No historical data available — this is the first pulse for this zip/business."}

Write a 3-5 paragraph trend narrative. Be specific about which weeks showed which patterns.
If no history is available, say so briefly and note that this is a baseline week."""


def _economist_instruction(ctx) -> str:
    state = getattr(ctx, "state", {})
    zip_code = state.get("zipCode", "")
    business_type = state.get("businessType", "")
    signals = state.get("rawSignals", {})

    # Extract economic signals
    sections = []
    if signals.get("blsCpi"):
        sections.append(f"BLS CPI: {json.dumps(signals['blsCpi'], default=str)[:2000]}")
    if signals.get("priceDeltas"):
        sections.append(f"Price Deltas: {json.dumps(signals['priceDeltas'], default=str)[:1500]}")
    if signals.get("censusDemographics"):
        sections.append(f"Census: {json.dumps(signals['censusDemographics'], default=str)[:1500]}")
    if signals.get("irsIncome"):
        sections.append(f"IRS Income: {json.dumps(signals['irsIncome'], default=str)[:1000]}")
    if signals.get("sbaLoans"):
        sections.append(f"SBA Loans: {json.dumps(signals['sbaLoans'], default=str)[:1000]}")
    if signals.get("qcewEmployment"):
        sections.append(f"QCEW Employment: {json.dumps(signals['qcewEmployment'], default=str)[:1500]}")
    if signals.get("housePriceIndex"):
        sections.append(f"FHFA HPI: {json.dumps(signals['housePriceIndex'], default=str)[:500]}")
    if signals.get("healthMetrics"):
        sections.append(f"CDC PLACES: {json.dumps(signals['healthMetrics'], default=str)[:1000]}")
    if signals.get("trends"):
        sections.append(f"Google Trends: {json.dumps(signals['trends'], default=str)[:1000]}")

    pre_computed = state.get("preComputedImpact", {})
    if pre_computed:
        sections.append(f"Pre-Computed Impact: {json.dumps(pre_computed, default=str)}")

    signal_text = "\n\n".join(sections) if sections else "No economic data available."

    return f"""You are a Local Business Economist analyzing {business_type} in zip {zip_code}.

Review these economic and demographic signals and produce a macro report covering:
1. **Price pressure** — which costs are rising/falling and by how much
2. **Consumer spending power** — income trends, housing values, economic stress
3. **Labor market** — employment trends, new business formation
4. **Demand signals** — Google Trends, search interest shifts
5. **Competitive landscape** — establishment counts, saturation level

Current date: {datetime.now().strftime('%Y-%m-%d')}

ECONOMIC SIGNALS:
{signal_text}

Write a structured macro report (3-5 paragraphs). Cite specific numbers.
Do NOT make up data — if a source is missing, skip that section."""


def _local_scout_instruction(ctx) -> str:
    state = getattr(ctx, "state", {})
    zip_code = state.get("zipCode", "")
    city = state.get("city", "")
    st = state.get("state", "")
    business_type = state.get("businessType", "")
    signals = state.get("rawSignals", {})

    # Extract local signals
    sections = []
    if signals.get("weather"):
        w = signals["weather"]
        # Add freshness warning if weather data has a fetchedAt timestamp
        fetched_at = w.get("fetchedAt") or w.get("fetched_at", "")
        freshness_note = ""
        if fetched_at:
            try:
                from datetime import datetime as _dt
                fetched_time = _dt.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
                age_hours = (_dt.now(fetched_time.tzinfo) - fetched_time).total_seconds() / 3600
                if age_hours > 6:
                    freshness_note = f" [WARNING: forecast is {age_hours:.0f}h old — may be stale]"
            except Exception:
                pass
        sections.append(f"Weather{freshness_note}: {json.dumps(w, default=str)[:1500]}")
    if signals.get("weatherHistory"):
        sections.append(f"Weather Baseline: {json.dumps(signals['weatherHistory'], default=str)[:800]}")
    if signals.get("localNews"):
        articles = signals["localNews"].get("articles", [])[:8]
        sections.append(f"Local News ({len(articles)} articles): {json.dumps(articles, default=str)[:2000]}")
    if signals.get("legalNotices"):
        sections.append(f"Legal Notices: {json.dumps(signals['legalNotices'], default=str)[:1500]}")

    # OSM nearby businesses — feed competitor names to the LLM
    if signals.get("osmDensity"):
        osm = signals["osmDensity"]
        nearby = osm.get("nearby", [])
        if nearby:
            biz_lines = []
            for b in nearby[:15]:
                name = b.get("name", "?")
                cat = b.get("cuisine") or b.get("category", "")
                dist = b.get("distanceM", "?")
                biz_lines.append(f"- {name} ({cat}, {dist}m away)")
            saturation = osm.get("saturationLevel", "unknown")
            total = osm.get("totalBusinesses", 0)
            sections.append(
                f"Nearby Competitors ({total} total, saturation: {saturation}):\n"
                + "\n".join(biz_lines)
            )

    # LLM-gathered research (from Stage 1 ResearchFanOut)
    social = state.get("socialPulse", "")
    if social:
        sections.append(f"Social Pulse: {social[:2000] if isinstance(social, str) else json.dumps(social, default=str)[:2000]}")
    catalysts = state.get("localCatalysts", "")
    if catalysts:
        sections.append(f"Local Catalysts: {catalysts[:2000] if isinstance(catalysts, str) else json.dumps(catalysts, default=str)[:2000]}")

    signal_text = "\n\n".join(sections) if sections else "No local data available."

    return f"""You are a Local Scout for {business_type} businesses in {city}, {st} ({zip_code}).

Review these local signals and produce a ground-level report covering:
1. **This week's weather impact** — compare forecast to historical baseline, note unusual patterns
2. **Local events & catalysts** — construction, government decisions, community events
3. **Community sentiment** — what locals are talking about (from social pulse)
4. **News relevance** — any local news that could affect {business_type} businesses
5. **Physical changes** — road work, new developments, closures

Current date: {datetime.now().strftime('%Y-%m-%d')}

LOCAL SIGNALS:
{signal_text}

Write a structured local report. Be specific about timing.
Do NOT make up data — if a source is missing, skip that section.

Structure your report with these CLEARLY LABELED sections:
## EVENTS THIS WEEK
List each event with: name, venue, address (if known), date/time, relevance to {business_type}

## COMPETITOR OBSERVATIONS
Name SPECIFIC local businesses from the Nearby Competitors list. For each, note what they're doing (new menu, promotion, event, closure, opening). Cross-reference with local news and social pulse. Do NOT name national chains unless there's a specific local story about them.

## COMMUNITY SENTIMENT
What are locals saying on social media, Patch, Reddit?

## GOVERNMENT & INFRASTRUCTURE
Any road work, permits, zoning changes, planning board items?

## WEATHER IMPACT
This week's forecast vs historical baseline, impact on foot traffic"""


# ---------------------------------------------------------------------------
# Stage 2 sub-agents
# ---------------------------------------------------------------------------


_pulse_history_summarizer = LlmAgent(
    name="PulseHistorySummarizer",
    model=AgentModels.PRIMARY_MODEL,
    description="Analyzes 12-week pulse history for longitudinal trends.",
    instruction=_historian_instruction,
    output_key="trendNarrative",
    on_model_error_callback=fallback_on_error,
)

_economist_agent = LlmAgent(
    name="EconomistAgent",
    model=AgentModels.PRIMARY_MODEL,
    description="Distills economic and demographic signals into a macro report.",
    instruction=_economist_instruction,
    output_key="macroReport",
    on_model_error_callback=fallback_on_error,
)

_local_scout_agent = LlmAgent(
    name="LocalScoutAgent",
    model=AgentModels.PRIMARY_MODEL,
    description="Distills local weather, news, catalysts, and social signals.",
    instruction=_local_scout_instruction,
    output_key="localReport",
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Stage 2: PreSynthesis — all 3 experts run in parallel
# ---------------------------------------------------------------------------

pre_synthesis = ParallelAgent(
    name="PreSynthesis",
    sub_agents=[
        _pulse_history_summarizer,
        _economist_agent,
        _local_scout_agent,
    ],
)
