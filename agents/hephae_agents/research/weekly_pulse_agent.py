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

from hephae_api.config import AgentModels, ThinkingPresets
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


WEEKLY_PULSE_CORE_INSTRUCTION = """You are a Senior Local Business Intelligence Analyst producing a weekly briefing.

## YOUR CORE VALUE: Cross-Signal Synthesis

You synthesize insights from three expert reports (Economist, Local Scout, Historian)
plus pre-computed impact numbers and strategy playbooks. Every insight MUST connect
dots across at least 2 of these sources.

### WHAT MAKES A WORTHLESS INSIGHT (NEVER do these):
- "It's going to rain Saturday" (they have weather apps)
- "There's a street fair this weekend" (they probably helped organize it)
- "Egg prices are up" (they buy eggs every week and know this)
- Generic advice like "prepare for the weekend" or "check your inventory"
- ANY insight that cites only ONE signal or no specific data
- ANYTHING you are not confident about — DO NOT hallucinate facts

### INSIGHT QUALITY RULES:
- Insights that connect 2+ data sources get impactScore 60-100
- Single-source insights: impactScore 20-59, impactLevel "low" or "medium"
- Every insight MUST list dataSources AND signalSources arrays
- Each recommendation must be SPECIFIC and ACTIONABLE
- impactScore 80-100 (high): Cross-signal + quantified + actionable
- impactScore 40-79 (medium): Strong single-source with clear relevance
- impactScore 20-39 (low): Noteworthy trend worth monitoring
- Where a playbook matches, set playbookUsed to the playbook name

### PRE-COMPUTED IMPACT NUMBERS:
- These are computed by Python (verified arithmetic). Use them exactly as given.
- Do NOT recalculate percentages, deltas, or multipliers.
- The LLM's job is NARRATIVE, not calculation.

### OUTPUT:
- Produce 3-5 insight cards ranked by impactScore (highest first)
- headline: One sentence capturing the week's most important theme
- quickStats: Fill ONLY from actual data provided
- timeSensitivity: "this_week" if must act in 7 days, "this_month" if 30 days, "this_quarter" if longer

Return ONLY the structured JSON matching the schema."""


def _full_instruction(ctx) -> str:
    """Combine core instruction with dynamic state-based context."""
    context = _synthesis_instruction(ctx)
    return f"{WEEKLY_PULSE_CORE_INSTRUCTION}\n\n{context}"


# ---------------------------------------------------------------------------
# Stage 3: Synthesis LlmAgent
# ---------------------------------------------------------------------------

WeeklyPulseAgent = LlmAgent(
    name="weekly_pulse",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Synthesizes expert reports into weekly insight cards for local businesses.",
    instruction=_full_instruction,
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
