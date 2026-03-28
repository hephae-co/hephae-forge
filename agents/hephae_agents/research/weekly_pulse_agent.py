"""Stage 3: WeeklyPulseAgent — cross-signal synthesis with DEEP thinking.

This is the core synthesis LlmAgent. It reads pre-processed reports from
session.state (written by Stage 1 + Stage 2) and generates 3-5 ranked
insight cards.

Key differences from the old implementation:
- Does NOT build its own signal prompt — reads macroReport, localReport,
  trendNarrative, preComputedImpact, matchedPlaybooks from state
- Supports rewrite mode: when state["rewriteFeedback"] is set, revises
  only the failing insights instead of generating from scratch
- Uses output_key to write results back to session.state
- Uses native structured output via response_schema=WeeklyPulseOutput
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from google.adk.agents import LlmAgent
from google.genai import types as genai_types

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas import WeeklyPulseOutput

logger = logging.getLogger(__name__)


def _synthesis_instruction(ctx) -> str:
    """Build the synthesis instruction from session.state.

    Reads pre-processed domain expert reports instead of raw signals,
    plus pre-computed impact multipliers and matched playbooks.
    """
    state = getattr(ctx, "state", {})
    zip_code = state.get("zipCode", "")
    business_type = state.get("businessType", "")
    week_of = state.get("weekOf", "")

    # Domain expert reports (from Stage 2)
    macro_report = state.get("macroReport", "")
    local_report = state.get("localReport", "")
    trend_narrative = state.get("trendNarrative", "")

    # Pre-computed impact (from Stage 1, Python math)
    pre_computed = state.get("preComputedImpact", {})
    matched_playbooks = state.get("matchedPlaybooks", [])

    # Rewrite feedback (from Stage 4 critique loop)
    rewrite_feedback = state.get("rewriteFeedback", "")

    # Build the instruction
    sections = [
        f"ZIP CODE: {zip_code}",
        f"BUSINESS TYPE: {business_type}",
        f"WEEK OF: {week_of}",
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    # Industry-specific synthesis context
    industry_cfg = state.get("industryConfig", {})
    synthesis_context = industry_cfg.get("synthesisContext", "")
    if synthesis_context:
        sections.append(f"=== INDUSTRY CONTEXT ===")
        sections.append(synthesis_context)
        sections.append("")

    # Industry trend summary (from national industry pulse)
    industry_trend = state.get("industryTrendSummary", "")
    if industry_trend:
        sections.append("=== NATIONAL INDUSTRY TREND ===")
        sections.append(industry_trend)
        sections.append("")

    # Technology intelligence (from TechScout, pre-computed weekly)
    tech_intel = state.get("techIntelligence", {})
    if tech_intel:
        tech_parts = []
        highlight = tech_intel.get("weeklyHighlight")
        if highlight:
            tech_parts.append(f"**This week's tech highlight:** {highlight.get('title', '')} — {highlight.get('detail', '')}")
        ai_opps = tech_intel.get("aiOpportunities", [])
        if ai_opps:
            for opp in ai_opps[:2]:
                tech_parts.append(f"- {opp.get('tool', '')}: {opp.get('capability', '')} → {opp.get('actionForOwner', '')}")
        updates = tech_intel.get("platformUpdates", {})
        if updates:
            for cat, update in list(updates.items())[:3]:
                if update:
                    tech_parts.append(f"- {cat}: {update}")
        if tech_parts:
            sections.append("=== TECHNOLOGY INTELLIGENCE ===")
            sections.append("Include technology recommendations when relevant to insights.")
            sections.append("\n".join(tech_parts))
            sections.append("")

    # Rewrite mode — revise specific insights
    if rewrite_feedback:
        existing_output = state.get("pulseOutput", "")
        sections.append("=== REWRITE MODE ===")
        sections.append("You previously generated insights that failed quality review.")
        sections.append("Revise ONLY the failing insights based on this feedback:")
        sections.append(rewrite_feedback)
        sections.append("")
        if existing_output:
            sections.append("=== YOUR PREVIOUS OUTPUT ===")
            sections.append(json.dumps(existing_output, default=str)[:3000])
            sections.append("")
        sections.append(
            "Keep passing insights unchanged. Rewrite ONLY the ones flagged. "
            "Apply the specific feedback for each."
        )
        sections.append("")

    # Macro economic report
    if macro_report:
        sections.append("=== ECONOMIST REPORT ===")
        sections.append(macro_report if isinstance(macro_report, str) else json.dumps(macro_report, default=str))
        sections.append("")

    # Local ground-level report
    if local_report:
        sections.append("=== LOCAL SCOUT REPORT ===")
        sections.append(local_report if isinstance(local_report, str) else json.dumps(local_report, default=str))
        sections.append("")

    # Trend narrative (longitudinal)
    if trend_narrative:
        sections.append("=== TREND NARRATIVE (12-week history) ===")
        sections.append(trend_narrative if isinstance(trend_narrative, str) else json.dumps(trend_narrative, default=str))
        sections.append("")

    # Pre-computed impact numbers (Python math — use as facts, don't recalculate)
    if pre_computed:
        sections.append("=== PRE-COMPUTED IMPACT MULTIPLIERS (verified arithmetic) ===")
        sections.append("Use these pre-computed figures exactly as given. Do NOT recalculate.")
        sections.append(json.dumps(pre_computed, default=str, indent=2))
        sections.append("")

    # Matched playbooks
    if matched_playbooks:
        sections.append("=== MATCHED STRATEGY PLAYBOOKS ===")
        sections.append(
            "Where applicable, map your recommendations to these established plays. "
            "Set the playbookUsed field on insights that use a playbook."
        )
        for pb in matched_playbooks:
            sections.append(f"- [{pb['name']}] ({pb['category']}): {pb['play']}")
        sections.append("")

    # Raw signals available (for reference/detail)
    raw_signals = state.get("rawSignals", {})
    if raw_signals:
        signal_keys = [k for k, v in raw_signals.items() if v]
        sections.append(f"=== DATA SOURCES AVAILABLE: {', '.join(signal_keys)} ===")
        sections.append(
            "The expert reports above are distilled from these sources. "
            "If you need a specific data point, it's in the reports."
        )

    return "\n".join(sections)


WEEKLY_PULSE_CORE_INSTRUCTION = """You are a data analyst writing a weekly intelligence briefing for a local business owner. The owner is busy, skeptical, and allergic to fluff. They want to know exactly what changed, what the numbers say, and what to do about it THIS WEEK.

## RULES — VIOLATING ANY OF THESE MAKES THE INSIGHT WORTHLESS:

1. **EVERY insight MUST contain at least 2 specific numbers from the data.**
   BAD: "Food costs are rising, consider adjusting your menu"
   GOOD: "Dairy CPI is up 12.1% YoY while poultry is down 5.3% — swap your Wednesday cream pasta special ($4.20 food cost) for grilled chicken ($2.80 food cost), saving $1.40/plate"

2. **EVERY recommendation MUST be a concrete action, not advice.**
   BAD: "Consider diversifying your revenue streams"
   GOOD: "Add a $12.99 family meal deal for pickup on DoorDash — 71% of your competitors already offer delivery and 'meal prep delivery' searches are up 40% in your DMA"

3. **NEVER use these phrases:** "consider", "it's worth noting", "businesses should be aware", "stay informed", "monitor closely", "proactive approach", "strategic positioning", "capitalize on", "leverage". These are consultant-speak that says nothing.

4. **NEVER write an insight about something the owner already knows.** They live there. They buy groceries. They watch the weather. Your value is CONNECTING data they can't see — BLS indexes, Census trends, OSM competition counts, SBA loan volumes, Google search trends.

5. **EVERY analysis paragraph must follow this structure:**
   - WHAT changed (with specific number from the data)
   - WHY it matters for THIS business (cross-reference with another signal)
   - WHAT to do about it (specific action with expected outcome)

## GOOD INSIGHT EXAMPLE:
Title: "Swap cream-heavy specials to grilled protein this month"
Analysis: "BLS CPI shows dairy up 12.1% YoY (index 283.4, Feb 2026) while poultry dropped 5.3%. Your zip code's median household income is $95,259 (Census ACS), meaning customers can absorb a $1-2 price increase on premium items but will notice margin erosion on staples. OSM shows 10 restaurants within 1500m — 3 added delivery in the past quarter."
Recommendation: "Replace your top 3 cream/cheese-heavy menu items with grilled protein alternatives this week. At current BLS prices, this saves approximately $1.40/plate on food cost. Post the menu change on Instagram with 'fresh spring menu' positioning — 'outdoor dining' searches are up in your DMA."

## BAD INSIGHT EXAMPLE (DO NOT PRODUCE ANYTHING LIKE THIS):
Title: "Volume Capture Opportunity from Local Events"
Analysis: "The current trend demands a shift from passive expectation of event-related traffic to aggressive conversion of the post-event crowd..."
WHY IT'S BAD: No numbers, no specific data citations, reads like a business school essay, says "consider" and "capitalize", owner already knows about local events.

## LOCAL BRIEFING (REQUIRED — this is what makes your report worth reading)

You MUST populate the localBriefing section from the Local Scout Report and Social Pulse data.

### thisWeekInTown (events happening THIS week)
Extract every event, opening, closure, or happening from the local data.
Each event MUST have: what (event name + venue), where (address), when (day/time), businessImpact (1 sentence: how this affects a restaurant), source.
Example:
  what: "Italian Language Exchange at Aromi Di Napoli"
  where: "246 Washington Ave"
  when: "Saturday March 21, morning"
  businessImpact: "Foot traffic boost on Washington Ave — run a brunch special if you're nearby"
  source: "NJBulletin.com via Social Pulse"

### competitorWatch (what nearby businesses are doing)
Extract observations about NAMED local businesses from social pulse, news, and OSM data.
Each note MUST name a specific business — not "local restaurants" or "competitors".
Example:
  business: "Luna Wood Fire Tavern"
  observation: "Shifting marketing to spring private event bookings"
  implication: "Private event season starting — add a catering/events page if you don't have one"
  source: "Social Pulse"

### communityBuzz
2-3 sentences summarizing what locals are discussing. Must reference specific sources (Reddit, Patch, social media). If nothing found, say "No significant local chatter this week."

### governmentWatch
Planning board decisions, permits, road work, zoning changes. If nothing found, say "No government actions affecting restaurants this week."

DO NOT leave localBriefing empty if there is ANY local data in the reports. Even one event or one competitor mention counts.

## OUTPUT:
- Produce 5-8 insight cards ranked by impactScore (highest first)
- headline: One punchy sentence with a NUMBER in it (e.g., "Dairy up 12% while 3 new competitors added delivery — time to pivot")
- quickStats: Fill ONLY from actual data provided
- timeSensitivity: "this_week" | "this_month" | "this_quarter"
- signalSources: list the actual source keys (e.g., ["blsCpi", "census", "osmDensity"])
- playbookUsed: set if a matched playbook applies
- impactScore 80-100: Cross-signal, quantified, specific action
- impactScore 50-79: Strong single source with clear business relevance
- impactScore 20-49: Noteworthy data point worth knowing

## PRE-COMPUTED NUMBERS:
The numbers in the PRE-COMPUTED IMPACT section are verified Python arithmetic. Use them as FACTS. Do NOT recalculate. Do NOT round differently. Cite them exactly.

Return ONLY the structured JSON matching the schema."""


def _synthesis_before_model(callback_context, llm_request):
    """Inject dynamic synthesis context (domain reports, playbooks, etc.) into the model request.

    This replaces the callable _full_instruction pattern, allowing the static
    WEEKLY_PULSE_CORE_INSTRUCTION to be cached across zip codes.
    """
    state = callback_context.state
    context_text = _synthesis_instruction_from_state(state)
    llm_request.contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=context_text)])
    )
    return None


def _synthesis_instruction_from_state(state: dict) -> str:
    """Build synthesis context from a state dict (shared by callback and standalone)."""
    zip_code = state.get("zipCode", "")
    business_type = state.get("businessType", "")
    week_of = state.get("weekOf", "")

    macro_report = state.get("macroReport", "")
    local_report = state.get("localReport", "")
    trend_narrative = state.get("trendNarrative", "")
    pre_computed = state.get("preComputedImpact", {})
    matched_playbooks = state.get("matchedPlaybooks", [])
    rewrite_feedback = state.get("rewriteFeedback", "")

    sections = [
        f"ZIP CODE: {zip_code}",
        f"BUSINESS TYPE: {business_type}",
        f"WEEK OF: {week_of}",
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    industry_cfg = state.get("industryConfig", {})
    synthesis_context = industry_cfg.get("synthesisContext", "")
    if synthesis_context:
        sections.append("=== INDUSTRY CONTEXT ===")
        sections.append(synthesis_context)
        sections.append("")

    industry_trend = state.get("industryTrendSummary", "")
    if industry_trend:
        sections.append("=== NATIONAL INDUSTRY TREND ===")
        sections.append(industry_trend)
        sections.append("")

    tech_intel = state.get("techIntelligence", {})
    if tech_intel:
        tech_parts = []
        highlight = tech_intel.get("weeklyHighlight")
        if highlight:
            tech_parts.append(f"**This week's tech highlight:** {highlight.get('title', '')} — {highlight.get('detail', '')}")
        ai_opps = tech_intel.get("aiOpportunities", [])
        if ai_opps:
            for opp in ai_opps[:2]:
                tech_parts.append(f"- {opp.get('tool', '')}: {opp.get('capability', '')} → {opp.get('actionForOwner', '')}")
        updates = tech_intel.get("platformUpdates", {})
        if updates:
            for cat, update in list(updates.items())[:3]:
                if update:
                    tech_parts.append(f"- {cat}: {update}")
        if tech_parts:
            sections.append("=== TECHNOLOGY INTELLIGENCE ===")
            sections.append("Include technology recommendations when relevant to insights.")
            sections.append("\n".join(tech_parts))
            sections.append("")

    if rewrite_feedback:
        existing_output = state.get("pulseOutput", "")
        sections.append("=== REWRITE MODE ===")
        sections.append("You previously generated insights that failed quality review.")
        sections.append("Revise ONLY the failing insights based on this feedback:")
        sections.append(rewrite_feedback)
        sections.append("")
        if existing_output:
            sections.append("=== YOUR PREVIOUS OUTPUT ===")
            sections.append(json.dumps(existing_output, default=str)[:3000])
            sections.append("")
        sections.append(
            "Keep passing insights unchanged. Rewrite ONLY the ones flagged. "
            "Apply the specific feedback for each."
        )
        sections.append("")

    if macro_report:
        sections.append("=== ECONOMIST REPORT ===")
        sections.append(macro_report if isinstance(macro_report, str) else json.dumps(macro_report, default=str))
        sections.append("")

    if local_report:
        sections.append("=== LOCAL SCOUT REPORT ===")
        sections.append(local_report if isinstance(local_report, str) else json.dumps(local_report, default=str))
        sections.append("")

    if trend_narrative:
        sections.append("=== TREND NARRATIVE (12-week history) ===")
        sections.append(trend_narrative if isinstance(trend_narrative, str) else json.dumps(trend_narrative, default=str))
        sections.append("")

    if pre_computed:
        sections.append("=== PRE-COMPUTED IMPACT MULTIPLIERS (verified arithmetic) ===")
        sections.append("Use these pre-computed figures exactly as given. Do NOT recalculate.")
        sections.append(json.dumps(pre_computed, default=str, indent=2))
        sections.append("")

    if matched_playbooks:
        sections.append("=== MATCHED STRATEGY PLAYBOOKS ===")
        sections.append(
            "Where applicable, map your recommendations to these established plays. "
            "Set the playbookUsed field on insights that use a playbook."
        )
        for pb in matched_playbooks:
            sections.append(f"- [{pb['name']}] ({pb['category']}): {pb['play']}")
        sections.append("")

    raw_signals = state.get("rawSignals", {})
    if raw_signals:
        signal_keys = [k for k, v in raw_signals.items() if v]
        sections.append(f"=== DATA SOURCES AVAILABLE: {', '.join(signal_keys)} ===")
        sections.append(
            "The expert reports above are distilled from these sources. "
            "If you need a specific data point, it's in the reports."
        )

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Stage 3: Synthesis LlmAgent — static instruction for caching
# ---------------------------------------------------------------------------

WeeklyPulseAgent = LlmAgent(
    name="weekly_pulse",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Synthesizes expert reports into weekly insight cards for local businesses.",
    instruction=WEEKLY_PULSE_CORE_INSTRUCTION,
    before_model_callback=_synthesis_before_model,
    output_key="pulseOutput",
    output_schema=WeeklyPulseOutput,
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Standalone runner (backward compat for non-ADK-tree usage)
# ---------------------------------------------------------------------------


async def generate_weekly_pulse(
    zip_code: str,
    business_type: str,
    week_of: str,
    signals: dict[str, Any],
    prior_pulse: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the WeeklyPulseAgent standalone (backward compat).

    For the new ADK pipeline, the agent is invoked via the orchestrator.
    This function is kept for direct testing and fallback.
    """
    from hephae_common.adk_helpers import run_agent_to_json

    logger.info(f"[WeeklyPulse] Generating pulse for {zip_code} / {business_type} / {week_of}")

    # Build a simplified prompt for standalone usage
    prompt = _build_standalone_prompt(zip_code, business_type, week_of, signals, prior_pulse)

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


def _build_standalone_prompt(
    zip_code: str,
    business_type: str,
    week_of: str,
    signals: dict[str, Any],
    prior_pulse: dict[str, Any] | None = None,
) -> str:
    """Build prompt for standalone (non-pipeline) usage."""
    sections: list[str] = [
        f"ZIP CODE: {zip_code}",
        f"BUSINESS TYPE: {business_type}",
        f"WEEK OF: {week_of}",
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "=== RAW SIGNALS (standalone mode — no expert reports available) ===",
    ]

    for key, value in signals.items():
        if value:
            content = json.dumps(value, default=str)[:2000]
            sections.append(f"--- {key} ---\n{content}\n")

    if prior_pulse:
        sections.append("=== PRIOR WEEK'S BRIEFING ===")
        prior = prior_pulse.get("pulse", prior_pulse)
        sections.append(f"Headline: {prior.get('headline', 'N/A')}")
        for insight in prior.get("insights", [])[:3]:
            sections.append(f"- [{insight.get('rank', '')}] {insight.get('title', '')}")
        sections.append("")

    sections.append(f"=== DATA SOURCES AVAILABLE: {', '.join(k for k in signals if signals[k])} ===")
    return "\n".join(sections)
