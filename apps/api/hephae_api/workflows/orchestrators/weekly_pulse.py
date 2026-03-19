"""Weekly Pulse orchestrator — ADK multi-agent pipeline for insight generation.

Replaced the previous 463-line asyncio.gather implementation with an ADK
SequentialAgent tree (PulseOrchestrator) that runs 4 stages:
  1. DataGatherer (parallel fetch + research)
  2. PreSynthesis (domain experts: economist, local scout, historian)
  3. Synthesis (WeeklyPulseAgent with DEEP thinking)
  4. Critique Loop (quality gate, max 2 iterations)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _truncate(obj: Any, max_len: int = 500) -> Any:
    """Truncate large values for diagnostics storage."""
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + f"... ({len(obj)} chars)"
    if isinstance(obj, list) and len(obj) > 10:
        return obj[:10] + [f"... ({len(obj)} items total)"]
    if isinstance(obj, dict):
        return {k: _truncate(v, max_len) for k, v in obj.items()}
    return obj


def _current_iso_week() -> str:
    """Return current ISO week string like '2026-W12'."""
    now = datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


async def generate_pulse(
    zip_code: str,
    business_type: str,
    week_of: str = "",
    force: bool = False,
    test_mode: bool = False,
) -> dict[str, Any]:
    """Main entry point for weekly pulse generation via ADK agent tree.

    Args:
        test_mode: When True, all persisted data gets a 24h TTL via expireAt
                   field and a testMode=True marker. Keeps test data separate
                   from production weekly runs.

    Returns:
        {"pulse": dict, "pulseId": str, "signalsUsed": list[str], "diagnostics": dict}
    """
    from hephae_db.firestore.weekly_pulse import get_latest_pulse, save_weekly_pulse
    from hephae_db.firestore.signal_archive import save_signal_archive
    from hephae_db.bigquery.public_data import resolve_zip_geography
    from hephae_db.firestore.weekly_pulse import get_pulse_history

    if not week_of:
        week_of = _current_iso_week()

    logger.info(f"[WeeklyPulse] Starting pulse for {zip_code} / {business_type} / {week_of}")
    started_at = datetime.utcnow()

    # 0. Check cache
    if not force:
        existing = await get_latest_pulse(zip_code, business_type)
        if existing and existing.get("weekOf") == week_of:
            logger.info(f"[WeeklyPulse] Returning cached pulse for {week_of}")
            return {
                "pulse": existing.get("pulse", {}),
                "pulseId": existing["id"],
                "signalsUsed": existing.get("signalsUsed", []),
                "diagnostics": existing.get("diagnostics", {}),
            }

    # 1. Resolve geography (BQ — authoritative)
    geo = await resolve_zip_geography(zip_code)
    city = geo.city if geo else ""
    state = geo.state_code if geo else ""
    county = geo.county if geo else ""
    latitude = geo.latitude if geo else 0.0
    longitude = geo.longitude if geo else 0.0

    # DMA mapping
    STATE_TO_DMA = {
        "NJ": "New York", "NY": "New York", "CT": "New York",
        "PA": "Philadelphia", "DE": "Philadelphia",
        "CA": "Los Angeles", "IL": "Chicago", "TX": "Dallas",
        "MA": "Boston", "FL": "Miami", "GA": "Atlanta",
        "WA": "Seattle", "CO": "Denver", "AZ": "Phoenix",
        "DC": "Washington", "MD": "Washington", "VA": "Washington",
    }
    dma_name = STATE_TO_DMA.get(state, "")

    # 2. Load pulse history for longitudinal context
    history = await get_pulse_history(zip_code, business_type, limit=12)

    # 3. Build initial session state
    initial_state = {
        "zipCode": zip_code,
        "businessType": business_type,
        "weekOf": week_of,
        "city": city,
        "state": state,
        "county": county,
        "latitude": latitude,
        "longitude": longitude,
        "dmaName": dma_name,
        "pulseHistory": [p.get("diagnostics", {}) for p in history],
        "pulseHistoryInsights": [
            p.get("pulse", {}).get("insights", []) for p in history
        ],
    }

    # 4. Run ADK agent tree
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from hephae_common.adk_helpers import user_msg
    from hephae_agents.research.pulse_orchestrator import create_pulse_orchestrator

    orchestrator = create_pulse_orchestrator()
    session_service = InMemorySessionService()
    runner = Runner(
        agent=orchestrator,
        app_name="weekly_pulse",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="weekly_pulse",
        user_id="system",
        state=initial_state,
    )

    logger.info(f"[WeeklyPulse] Running ADK pipeline for {zip_code}")
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_msg(
            f"Generate weekly pulse for {zip_code} ({business_type}), week of {week_of}."
        ),
    ):
        pass  # Pipeline runs through all 4 stages

    # 5. Re-fetch session to get final state (local object may be stale)
    session = await session_service.get_session(
        app_name="weekly_pulse",
        user_id="system",
        session_id=session.id,
    )
    final_state = dict(session.state or {})
    logger.info(
        f"[WeeklyPulse] Pipeline complete — state keys: {list(final_state.keys())}"
    )

    pulse_output = final_state.get("pulseOutput")
    critique_result = final_state.get("critiqueResult")
    raw_signals = final_state.get("rawSignals", {})
    signals_used = final_state.get("signalsUsed", [])
    pre_computed = final_state.get("preComputedImpact", {})
    matched_playbooks = final_state.get("matchedPlaybooks", [])

    # Parse pulse output
    if isinstance(pulse_output, str):
        try:
            pulse_output = json.loads(pulse_output)
        except (json.JSONDecodeError, ValueError):
            pulse_output = {}

    if not pulse_output or not isinstance(pulse_output, dict):
        pulse_output = {
            "zipCode": zip_code,
            "businessType": business_type,
            "weekOf": week_of,
            "headline": "Insufficient data to generate pulse this week.",
            "insights": [],
            "quickStats": {},
        }

    pulse_output.setdefault("zipCode", zip_code)
    pulse_output.setdefault("businessType", business_type)
    pulse_output.setdefault("weekOf", week_of)

    # Parse critique
    critique_pass = True
    critique_score = 0
    if critique_result:
        if isinstance(critique_result, str):
            try:
                critique_result = json.loads(critique_result)
            except (json.JSONDecodeError, ValueError):
                critique_result = {}
        if isinstance(critique_result, dict):
            critique_pass = critique_result.get("overall_pass", True)
            insight_critiques = critique_result.get("insights", [])
            if insight_critiques:
                scores = [
                    ic.get("actionability_score", 0) + ic.get("cross_signal_score", 0)
                    - ic.get("obviousness_score", 0)
                    for ic in insight_critiques
                ]
                critique_score = int(sum(scores) / len(scores)) if scores else 0

    # 6. Build diagnostics
    diagnostics: dict[str, Any] = {
        "startedAt": started_at.isoformat(),
        "completedAt": datetime.utcnow().isoformat(),
        "signalCount": len(signals_used),
        "insightCount": len(pulse_output.get("insights", [])),
        "critiquePass": critique_pass,
        "critiqueScore": critique_score,
        "playbooksMatched": [pb.get("name", "") for pb in matched_playbooks],
        "preComputedKeys": list(pre_computed.keys()),
        "pipeline": "adk_multi_agent_v2",
    }

    # 7. Build pipeline details from session state
    def _parse_state_text(key: str) -> str:
        val = final_state.get(key, "")
        if isinstance(val, dict):
            return json.dumps(val, default=str)
        return str(val) if val else ""

    pipeline_details = {
        "macroReport": _parse_state_text("macroReport"),
        "localReport": _parse_state_text("localReport"),
        "trendNarrative": _parse_state_text("trendNarrative"),
        "socialPulse": _parse_state_text("socialPulse"),
        "localCatalysts": _parse_state_text("localCatalysts"),
        "preComputedImpact": pre_computed,
        "matchedPlaybooks": matched_playbooks,
        "critiqueResult": critique_result if isinstance(critique_result, dict) else {},
        "rawSignals": {k: _truncate(v, 2000) for k, v in raw_signals.items() if v},
    }

    # 8. Save pulse + pipeline details + archive signals
    #    In test mode, set a 24h TTL so test data auto-cleans
    from datetime import timedelta
    test_ttl = datetime.utcnow() + timedelta(hours=24) if test_mode else None

    pulse_id = await save_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        pulse=pulse_output,
        signals_used=signals_used,
        diagnostics=diagnostics,
        pipeline_details=pipeline_details,
        test_mode=test_mode,
        expire_at=test_ttl,
    )

    logger.info(
        f"[WeeklyPulse] rawSignals keys: {list(raw_signals.keys())}, "
        f"total size: {sum(len(str(v)) for v in raw_signals.values())}"
    )

    if raw_signals:
        archive_sources = {}
        for source_name, data in raw_signals.items():
            if data:
                archive_sources[source_name] = {
                    "raw": _truncate(data, 5000),
                    "fetchedAt": datetime.utcnow().isoformat(),
                    "version": "v1",
                }
        await save_signal_archive(zip_code, week_of, archive_sources, pre_computed)

    logger.info(
        f"[WeeklyPulse] Pulse saved as {pulse_id} — "
        f"{len(pulse_output.get('insights', []))} insights, "
        f"critique={'PASS' if critique_pass else 'FAIL'}, "
        f"{len(signals_used)} signals"
    )

    return {
        "pulse": pulse_output,
        "pulseId": pulse_id,
        "signalsUsed": signals_used,
        "diagnostics": diagnostics,
        "pipelineDetails": pipeline_details,
    }
