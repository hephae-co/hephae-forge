"""Industry pulse generator — fetches national signals and produces a weekly
industry-level intelligence summary.

Runs once per industry per week (Monday 10:00 UTC), BEFORE zip-level pulses.
Zip pulses load the output of this step instead of re-fetching BLS/USDA/FDA.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _current_iso_week() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


async def generate_industry_pulse(
    industry_key: str,
    week_of: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Generate a national industry pulse.

    1. Check cache (skip if already exists for this week unless force=True)
    2. Fetch national signals (BLS CPI, USDA, FDA, price deltas)
    3. Compute impact multipliers from national data
    4. Match industry playbooks
    5. Generate a short LLM trend summary
    6. Save to Firestore

    Returns the saved pulse dict.
    """
    from hephae_db.firestore.industry_pulse import (
        get_industry_pulse,
        save_industry_pulse,
    )
    from hephae_api.workflows.orchestrators.industries import resolve, RESTAURANT
    from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_national_signals
    from hephae_api.workflows.orchestrators.pulse_playbooks import (
        compute_impact_multipliers,
        match_playbooks,
        match_industry_playbooks,
    )

    if not week_of:
        week_of = _current_iso_week()

    # Check cache
    if not force:
        existing = await get_industry_pulse(industry_key, week_of)
        if existing:
            logger.info(f"[IndustryPulse] Cache hit for {industry_key}-{week_of}")
            return existing

    # Resolve industry config
    industry = resolve(industry_key)
    if industry is RESTAURANT and industry_key != "restaurant":
        # Fallback happened — log but continue
        logger.warning(f"[IndustryPulse] No config for '{industry_key}', using restaurant fallback")

    started_at = datetime.utcnow().isoformat()

    # Fetch national signals using IndustryConfig.bls_series directly
    # so we get the correct series for each industry (not the BLS client's
    # hardcoded mapping which only covers restaurant/bakery/barber).
    logger.info(f"[IndustryPulse] Fetching national signals for {industry_key}")
    business_type = industry_key
    national_signals = await fetch_national_signals(
        business_type,
        state="US",  # national query — FDA/USDA use no state filter
        config_bls_series=dict(industry.bls_series) if industry.bls_series else None,
    )

    signals_used = [k for k, v in national_signals.items() if v]

    # Compute impact multipliers (national subset only)
    national_impact = compute_impact_multipliers(national_signals)

    # Match playbooks: IndustryConfig-specific first, then generic fallback
    national_playbooks = match_industry_playbooks(industry.playbooks, national_impact)
    if not national_playbooks:
        # Fall back to global playbook registry if industry config has no playbooks
        national_playbooks = match_playbooks(national_impact, national_signals, business_type)

    # Generate LLM trend summary
    trend_summary = await _generate_trend_summary(
        industry_key, industry.name, national_signals, national_impact, national_playbooks,
    )

    completed_at = datetime.utcnow().isoformat()

    diagnostics = {
        "startedAt": started_at,
        "completedAt": completed_at,
        "signalCount": len(signals_used),
        "playbooksMatched": [p.get("name", "") for p in national_playbooks],
        "pipeline": "industry_pulse_v1",
    }

    # Save
    pulse_id = await save_industry_pulse(
        industry_key=industry_key,
        week_of=week_of,
        national_signals=national_signals,
        national_impact=national_impact,
        national_playbooks=national_playbooks,
        trend_summary=trend_summary,
        signals_used=signals_used,
        diagnostics=diagnostics,
    )

    logger.info(
        f"[IndustryPulse] Generated {pulse_id}: "
        f"{len(signals_used)} signals, {len(national_playbooks)} playbooks"
    )

    return {
        "id": pulse_id,
        "industryKey": industry_key,
        "weekOf": week_of,
        "nationalSignals": national_signals,
        "nationalImpact": national_impact,
        "nationalPlaybooks": national_playbooks,
        "trendSummary": trend_summary,
        "signalsUsed": signals_used,
        "diagnostics": diagnostics,
    }


async def _generate_trend_summary(
    industry_key: str,
    industry_name: str,
    signals: dict[str, Any],
    impact: dict[str, Any],
    playbooks: list[dict],
) -> str:
    """Generate a 2-3 paragraph national trend summary via a single LLM call."""
    try:
        from hephae_common.adk_helpers import run_agent_to_text
        from hephae_common.model_config import AgentModels
        from hephae_common.model_fallback import fallback_on_error
        from google.adk.agents import LlmAgent

        # Build context
        impact_lines = "\n".join(f"  {k}: {v}" for k, v in sorted(impact.items()) if isinstance(v, (int, float)))
        playbook_lines = "\n".join(
            f"  - {p.get('name', '?')}: {p.get('play', '')[:120]}"
            for p in playbooks
        )

        prompt = f"""Summarize the national economic signals for the {industry_name} industry this week.

PRE-COMPUTED IMPACT VARIABLES:
{impact_lines}

TRIGGERED PLAYBOOKS:
{playbook_lines or "  (none triggered)"}

Write 2-3 paragraphs. Lead with the most actionable signal. Include specific numbers.
Do NOT give advice — just summarize what the data shows. This will be combined with
local zip-code data downstream."""

        agent = LlmAgent(
            name="industry_trend_summarizer",
            model=AgentModels.PRIMARY_MODEL,
            instruction="You are a concise economic analyst. Summarize data signals in 2-3 paragraphs with specific numbers. No advice, just facts.",
            on_model_error_callback=fallback_on_error,
        )

        result = await run_agent_to_text(agent, prompt, app_name="industry_pulse")
        return result or ""

    except Exception as e:
        logger.error(f"[IndustryPulse] Trend summary failed for {industry_key}: {e}")
        return ""
