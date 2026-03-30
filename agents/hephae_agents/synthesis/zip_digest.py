"""Zip Weekly Digest ADK agents — synthesize zip pulse + industry digest + signals into a weekly brief.

Pipeline: ZipDataLoader (BaseAgent) → ZipSynthesizer (LlmAgent) → ZipDigestAssembler (BaseAgent)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types as genai_types

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


# ── Stage 1: Data Loader (deterministic) ──────────────────────────────────

class ZipDataLoader(BaseAgent):
    """Load zip pulse + industry digest + cached signals + profile + research."""

    name: str = "ZipDataLoader"
    description: str = "Loads all data sources for zip digest synthesis."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        zip_code = state.get("zipCode", "")
        business_type = state.get("businessType", "")
        week_of = state.get("weekOf", "")
        industry_key = state.get("industryKey", "")

        logger.info(f"[ZipDigest] Loading data for {zip_code} ({business_type}, {week_of})")

        # Load zip pulse — try exact business type first, then any pulse for this zip
        from hephae_db.firestore.weekly_pulse import get_latest_pulse
        zip_pulse = await get_latest_pulse(zip_code, business_type)
        if not zip_pulse:
            # Fallback: try loading any recent pulse for this zip (different business type)
            from hephae_common.firebase import get_db as _get_db
            _db = _get_db()
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter
                fallback_docs = await asyncio.to_thread(
                    lambda: list(_db.collection("zipcode_weekly_pulse").where(
                        filter=FieldFilter("zipCode", "==", zip_code)
                    ).limit(1).get())
                )
                if fallback_docs:
                    zip_pulse = fallback_docs[0].to_dict()
                    zip_pulse["id"] = fallback_docs[0].id
                    logger.info(f"[ZipDigest] Using fallback pulse {zip_pulse['id']} for {zip_code}")
            except Exception:
                pass

        # Extract pulse content — handle both flat and nested structures
        pulse_content = zip_pulse.get("pulse", zip_pulse) if zip_pulse else {}
        local_briefing = pulse_content.get("localBriefing", {})

        # Extract events from localBriefing.thisWeekInTown or pulse.events
        events = local_briefing.get("thisWeekInTown", []) or pulse_content.get("events", [])
        # Extract community buzz from localBriefing or pulse top-level
        community_buzz = local_briefing.get("communityBuzz", "") or pulse_content.get("communityBuzz", "")
        # Extract competitor watch
        competitor_watch = local_briefing.get("competitorWatch", [])

        # Load industry digest (pre-generated)
        from hephae_db.firestore.industry_digests import get_latest_industry_digest
        industry_digest = await get_latest_industry_digest(industry_key) if industry_key else None

        # Load cached signals
        from hephae_common.firebase import get_db
        db = get_db()
        signals: dict[str, Any] = {}
        for key in [f"irs:{zip_code}", f"weather:{zip_code}", f"census:{zip_code}"]:
            try:
                doc = await asyncio.to_thread(db.collection("data_cache").document(key).get)
                if doc.exists:
                    signals[key.split(":")[0]] = doc.to_dict().get("data", {})
            except Exception:
                pass

        # Load zipcode profile
        from hephae_db.firestore.zipcode_profiles import get_zipcode_profile
        profile = await get_zipcode_profile(zip_code)

        # Load research key facts
        research_facts: list[str] = []
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            results = await asyncio.to_thread(
                lambda: list(db.collection("zipcode_research").where(
                    filter=FieldFilter("zipCode", "==", zip_code)
                ).limit(1).get())
            )
            if results:
                report = results[0].to_dict().get("report", {})
                sections = report.get("sections", {})
                for sec_key in ["business_landscape", "consumer_market", "economic_indicators"]:
                    sec = sections.get(sec_key, {})
                    if isinstance(sec, dict):
                        research_facts.extend(sec.get("key_facts", [])[:2])
        except Exception:
            pass

        # Build weather outlook as a sentence, not just "high"
        weather_data = signals.get("weather", {})
        weather_fav = str(weather_data.get("outdoorFavorability", "")).lower()
        weather_outlook = (
            "Great outdoor conditions — expect higher foot traffic" if weather_fav in ("high", "very high")
            else "Poor outdoor conditions — expect lower walk-in traffic" if weather_fav in ("low", "very low")
            else f"Moderate outdoor conditions" if weather_fav else None
        )

        # Build local facts + intel via shared utility
        from hephae_common.local_facts import build_local_facts, build_local_intel
        local_facts = build_local_facts(
            signals.get("irs", {}),
            weather_data,
            signals.get("census", {}),
            research_facts[:6],
        )
        local_intel = build_local_intel(signals.get("irs", {}), signals.get("census", {}))

        # Log what we found
        logger.info(
            f"[ZipDigest] Loaded: pulse={'yes' if zip_pulse else 'no'}, "
            f"industry={'yes' if industry_digest else 'no'}, "
            f"events={len(events)}, buzz={'yes' if community_buzz else 'no'}, "
            f"facts={len(local_facts)}, weather={weather_outlook}"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={
                "rawZipPulse": zip_pulse or {},
                "pulseContent": pulse_content,
                "extractedEvents": events,
                "extractedBuzz": community_buzz,
                "extractedCompetitorWatch": competitor_watch,
                "industryDigest": industry_digest or {},
                "localFacts": local_facts,
                "localIntel": local_intel,
                "weatherOutlook": weather_outlook,
                "confirmedSources": (profile or {}).get("confirmedSources", 0),
            }),
        )


# ── Stage 2: LLM Synthesizer ─────────────────────────────────────────────

ZIP_SYNTH_INSTRUCTION = """You are a local business advisor writing a weekly brief. Given the data below, write:

1. A **weeklyBrief** (3-4 paragraphs): What matters this week for a {businessType} owner
   in {city}, {state}. Be specific — cite actual numbers, event names, competitor names,
   and price changes. Don't be generic. Write as if talking directly to the owner.

2. **actionItems** (3-5 items): Concrete things the owner should DO this week. Each should
   be a specific, actionable sentence starting with a verb.

Return as JSON: {"weeklyBrief": "...", "actionItems": ["...", "..."]}
"""


def _zip_synth_before_model(callback_context: Any, llm_request: Any) -> None:
    """Inject all loaded zip data into the model request."""
    state = callback_context.state
    pulse_content = state.get("pulseContent", {})
    industry = state.get("industryDigest", {})
    local_facts = state.get("localFacts", [])
    local_intel = state.get("localIntel", {})
    events = state.get("extractedEvents", [])
    buzz = state.get("extractedBuzz", "")
    competitor_watch = state.get("extractedCompetitorWatch", [])
    weather_outlook = state.get("weatherOutlook", "")

    parts = []

    # Pulse insights
    insights = pulse_content.get("insights", pulse_content.get("topInsights", []))
    if insights:
        insight_text = "\n".join(
            f"- [{ins.get('impactLevel', '?')}] {ins.get('title', '?')}: {ins.get('recommendation', '')[:150]}"
            for ins in insights[:5]
        )
        parts.append(f"Weekly Insights:\n{insight_text}")

    # Events
    if events:
        event_items = []
        for e in events[:5]:
            if isinstance(e, dict):
                event_items.append(f"- {e.get('what', e.get('event', '?'))} ({e.get('when', e.get('date', '?'))})")
            elif isinstance(e, str):
                event_items.append(f"- {e}")
        parts.append(f"Local Events:\n" + "\n".join(event_items))

    # Community buzz
    if buzz:
        parts.append(f"Community Buzz: {buzz}")

    # Competitor watch
    if competitor_watch:
        comp_items = []
        for c in competitor_watch[:5]:
            if isinstance(c, dict):
                comp_items.append(f"- {c.get('name', '?')}: {c.get('change', c.get('observation', '?'))}")
        if comp_items:
            parts.append(f"Competitor Activity:\n" + "\n".join(comp_items))

    # Weather
    if weather_outlook:
        parts.append(f"Weather: {weather_outlook}")

    # Industry context
    if industry.get("narrative"):
        parts.append(f"National Industry Context:\n{industry['narrative'][:500]}")

    # Local facts
    if local_facts:
        parts.append(f"Local Data Points:\n" + "\n".join(f"- {f}" for f in local_facts))

    # Local intel
    if local_intel:
        parts.append(f"Market Signals: " + ", ".join(f"{k}={v}" for k, v in local_intel.items()))

    context = "\n\n".join(parts) if parts else "Limited data available."

    # Inject dynamic instruction with city/state
    city = state.get("city", "")
    state_abbr = state.get("state", "")
    business_type = state.get("businessType", "")

    instruction = ZIP_SYNTH_INSTRUCTION.replace("{businessType}", business_type).replace("{city}", city).replace("{state}", state_abbr)

    llm_request.config = llm_request.config or genai_types.GenerateContentConfig()
    llm_request.config.system_instruction = instruction

    llm_request.contents.append(
        genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=context)],
        )
    )


def _create_zip_synthesizer() -> LlmAgent:
    return LlmAgent(
        name="ZipSynthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes zip-level data into a weekly brief.",
        instruction=ZIP_SYNTH_INSTRUCTION,
        before_model_callback=_zip_synth_before_model,
        output_key="synthOutput",
        on_model_error_callback=fallback_on_error,
    )


# ── Stage 3: Digest Assembler (deterministic) ────────────────────────────

class ZipDigestAssembler(BaseAgent):
    """Merge LLM brief + raw data into the final zip digest schema."""

    name: str = "ZipDigestAssembler"
    description: str = "Assembles the final zip weekly digest document."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        synth_raw = state.get("synthOutput", "")
        pulse = state.get("rawZipPulse", {})
        industry = state.get("industryDigest", {})

        # Parse LLM output
        weekly_brief = ""
        action_items: list[str] = []
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', synth_raw)
            if json_match:
                parsed = json.loads(json_match.group())
                weekly_brief = parsed.get("weeklyBrief", synth_raw)
                action_items = parsed.get("actionItems", [])
            else:
                weekly_brief = synth_raw
        except (json.JSONDecodeError, AttributeError):
            weekly_brief = synth_raw

        pulse_content = state.get("pulseContent", {})

        # Build AI tools from industry digest
        ai_tools = industry.get("aiTools", [])[:5]

        # Extract insights from pulse content
        raw_insights = pulse_content.get("insights") or pulse_content.get("topInsights") or []
        insights = [
            {
                "title": ins.get("title", ""),
                "recommendation": ins.get("recommendation", ""),
                "impactLevel": ins.get("impactLevel"),
            }
            for ins in raw_insights[:5]
            if isinstance(ins, dict)
        ]

        digest = {
            "industryKey": state.get("industryKey"),
            "city": state.get("city"),
            "state": state.get("state"),
            "county": state.get("county"),
            "confirmedSources": state.get("confirmedSources", 0),

            # LLM-synthesized
            "weeklyBrief": weekly_brief,
            "actionItems": action_items[:5],

            # From zip pulse (using extracted fields from ZipDataLoader)
            "headline": pulse_content.get("headline") or pulse_content.get("pulseHeadline"),
            "insights": insights,
            "events": state.get("extractedEvents", [])[:5],
            "communityBuzz": state.get("extractedBuzz") or None,
            "competitorWatch": state.get("extractedCompetitorWatch", []),

            # From industry digest (drop redundant nationalTrend — the brief already covers it)
            "playbooks": industry.get("playbooks", [])[:3],
            "keyMetrics": industry.get("nationalImpact", {}),

            # From tech intel (via industry digest)
            "techHighlight": industry.get("techHighlight"),
            "aiTools": ai_tools,

            # From data_cache
            "localFacts": state.get("localFacts", []),
            "localIntel": state.get("localIntel", {}),
            "weatherOutlook": state.get("weatherOutlook"),

            # Source tracking
            "sourcePulseId": pulse.get("id"),
            "sourceIndustryDigestId": industry.get("id"),
        }

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"zipDigest": digest}),
        )


# ── Factory ───────────────────────────────────────────────────────────────

def create_zip_digest_agent() -> SequentialAgent:
    """Create fresh agent tree for zip digest synthesis."""
    return SequentialAgent(
        name="ZipDigestPipeline",
        description="Synthesizes zip pulse + industry digest + signals into a weekly brief.",
        sub_agents=[
            ZipDataLoader(),
            _create_zip_synthesizer(),
            ZipDigestAssembler(),
        ],
    )
