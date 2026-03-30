"""Industry Digest ADK agents — synthesize industry pulse + tech intel into a reusable digest.

Pipeline: IndustryDataLoader (BaseAgent) → IndustrySynthesizer (LlmAgent) → IndustryDigestAssembler (BaseAgent)
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

class IndustryDataLoader(BaseAgent):
    """Load industry pulse + tech intelligence + AI tools from Firestore."""

    name: str = "IndustryDataLoader"
    description: str = "Loads raw data for industry digest synthesis."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        industry_key = state.get("industryKey", "")
        week_of = state.get("weekOf", "")

        logger.info(f"[IndustryDigest] Loading data for {industry_key} ({week_of})")

        # Load industry pulse
        from hephae_db.firestore.industry_pulse import get_industry_pulse
        industry_pulse = await get_industry_pulse(industry_key, week_of)

        # Load tech intelligence
        from hephae_db.firestore.tech_intelligence import get_tech_intelligence
        tech_intel = await get_tech_intelligence(industry_key, week_of)

        # Load AI tools for this vertical
        from hephae_db.firestore.ai_tools import get_tools_for_vertical
        ai_tools = await get_tools_for_vertical(industry_key, limit=10)

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={
                "rawIndustryPulse": industry_pulse or {},
                "rawTechIntel": tech_intel or {},
                "rawAiTools": ai_tools or [],
            }),
        )


# ── Stage 2: LLM Synthesizer ─────────────────────────────────────────────

INDUSTRY_SYNTH_INSTRUCTION = """You are an industry analyst. Given the raw data below, write:

1. A **narrative** (2-3 paragraphs): synthesize the national trends, commodity price movements,
   tech adoption patterns, and strategic implications for business owners in this industry.
   Be specific — cite actual numbers and percentages. Write for a busy owner, not an analyst.

2. **keyTakeaways** (3-5 bullet points): the most important things an owner should know this week.

Return as JSON: {"narrative": "...", "keyTakeaways": ["...", "..."]}
"""


def _industry_synth_before_model(callback_context: Any, llm_request: Any) -> None:
    """Inject loaded industry data into the model request."""
    state = callback_context.state
    pulse = state.get("rawIndustryPulse", {})
    tech = state.get("rawTechIntel", {})
    tools = state.get("rawAiTools", [])

    context_parts = []
    if pulse:
        context_parts.append(f"National Signals:\n{json.dumps(pulse.get('nationalSignals', {}), indent=1)}")
        context_parts.append(f"Impact Assessment:\n{json.dumps(pulse.get('nationalImpact', {}), indent=1)}")
        if pulse.get("trendSummary"):
            context_parts.append(f"Prior Trend Summary:\n{pulse['trendSummary']}")

    if tech:
        if tech.get("weeklyHighlight"):
            context_parts.append(f"Tech Highlight:\n{json.dumps(tech['weeklyHighlight'], indent=1)}")
        if tech.get("aiOpportunities"):
            context_parts.append(f"AI Opportunities:\n{json.dumps(tech['aiOpportunities'][:5], indent=1)}")

    if tools:
        tool_summary = [{"name": t.get("toolName"), "capability": t.get("aiCapability"), "isNew": t.get("weeksSeen", 99) <= 2} for t in tools[:5]]
        context_parts.append(f"AI Tools Catalog:\n{json.dumps(tool_summary, indent=1)}")

    context_text = "\n\n".join(context_parts) if context_parts else "No data available."

    llm_request.contents.append(
        genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=f"Industry: {state.get('industryKey', 'unknown')}\nWeek: {state.get('weekOf', '?')}\n\n{context_text}")],
        )
    )


def _create_industry_synthesizer() -> LlmAgent:
    return LlmAgent(
        name="IndustrySynthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes industry data into a narrative digest.",
        instruction=INDUSTRY_SYNTH_INSTRUCTION,
        before_model_callback=_industry_synth_before_model,
        output_key="synthOutput",
        on_model_error_callback=fallback_on_error,
    )


# ── Stage 3: Digest Assembler (deterministic) ────────────────────────────

class IndustryDigestAssembler(BaseAgent):
    """Merge LLM narrative + raw data into the final digest schema."""

    name: str = "IndustryDigestAssembler"
    description: str = "Assembles the final industry digest document."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        synth_raw = state.get("synthOutput", "")
        pulse = state.get("rawIndustryPulse", {})
        tech = state.get("rawTechIntel", {})
        tools = state.get("rawAiTools", [])

        # Parse LLM output
        narrative = ""
        key_takeaways: list[str] = []
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', synth_raw)
            if json_match:
                parsed = json.loads(json_match.group())
                narrative = parsed.get("narrative", synth_raw)
                key_takeaways = parsed.get("keyTakeaways", [])
            else:
                narrative = synth_raw
        except (json.JSONDecodeError, AttributeError):
            narrative = synth_raw

        # Build AI tools list
        ai_tools = []
        for opp in (tech.get("aiOpportunities") or [])[:5]:
            if isinstance(opp, dict):
                ai_tools.append({
                    "tool": opp.get("tool", ""),
                    "capability": opp.get("capability", ""),
                    "url": opp.get("url"),
                    "actionForOwner": opp.get("actionForOwner"),
                })

        # New tools this week
        new_tools = [
            {"name": t.get("toolName", ""), "capability": t.get("aiCapability", "")}
            for t in tools
            if isinstance(t, dict) and t.get("weeksSeen", 99) <= 2
        ][:5]

        digest = {
            "displayName": state.get("industryKey", "").replace("_", " ").title(),
            "narrative": narrative,
            "keyTakeaways": key_takeaways[:5],
            "nationalImpact": pulse.get("nationalImpact", {}),
            "playbooks": pulse.get("nationalPlaybooks", [])[:5],
            "signalsUsed": pulse.get("signalsUsed", []),
            "techHighlight": tech.get("weeklyHighlight", {}).get("title") if isinstance(tech.get("weeklyHighlight"), dict) else tech.get("weeklyHighlight"),
            "aiTools": ai_tools,
            "newToolsThisWeek": new_tools,
            "platformUpdates": tech.get("platforms", {}),
            "sourcePulseId": pulse.get("id"),
            "sourceTechIntelId": tech.get("id"),
        }

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"industryDigest": digest}),
        )


# ── Factory ───────────────────────────────────────────────────────────────

def create_industry_digest_agent() -> SequentialAgent:
    """Create fresh agent tree for industry digest synthesis."""
    return SequentialAgent(
        name="IndustryDigestPipeline",
        description="Synthesizes industry pulse + tech intel into a reusable digest.",
        sub_agents=[
            IndustryDataLoader(),
            _create_industry_synthesizer(),
            IndustryDigestAssembler(),
        ],
    )
