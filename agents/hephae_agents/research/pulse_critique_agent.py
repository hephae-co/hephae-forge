"""Stage 4: Critique Loop — LoopAgent wrapping critique + rewrite.

Architecture:
  CritiqueLoop (LoopAgent, max_iterations=2)
  └─ CritiqueSequence (SequentialAgent)
     ├─ PulseCritiqueAgent (LlmAgent) → evaluates pulseOutput
     ├─ CritiqueRouter (custom BaseAgent — deterministic, no LLM)
     │   if all pass: escalate → exits loop before rewrite runs
     │   if any fail: writes rewriteFeedback to state
     └─ WeeklyPulseAgent (rewrite mode) → reads rewriteFeedback, revises

The critique agent applies three tests per insight:
1. Walking Down the Street (obviousness) — score < 30 to pass
2. So What? (actionability) — score >= 70 to pass
3. Show Your Work (cross-signal reasoning) — score >= 60 to pass
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas import CritiqueResult

logger = logging.getLogger(__name__)


def _critique_instruction(ctx) -> str:
    """Build critique instruction from session.state."""
    state = getattr(ctx, "state", {})
    pulse_output = state.get("pulseOutput", "")

    pulse_text = ""
    if pulse_output:
        if isinstance(pulse_output, str):
            pulse_text = pulse_output
        else:
            pulse_text = json.dumps(pulse_output, default=str, indent=2)

    return f"""You are a Cynical Local Business Owner reviewing a weekly intelligence briefing.
You've run a restaurant for 15 years and can smell BS from a mile away.

Review each insight in the pulse output below and apply THREE TESTS:

## Test 1: Walking Down the Street (Obviousness)
"Would I already know this from living here and running my business?"
- Score 0-100 where HIGHER = MORE OBVIOUS (bad)
- "It's going to rain" = 95 (everyone has a weather app)
- "Dairy prices are up 12% YoY while poultry is down 5%" = 15 (I buy eggs but don't track BLS indexes)
- THRESHOLD: score must be < 30 to pass

## Test 2: So What? (Actionability)
"What specifically should I DO differently this week because of this?"
- Score 0-100 where HIGHER = MORE ACTIONABLE (good)
- "The economy is changing" = 10 (so what?)
- "Switch your Wednesday special from cream pasta to grilled chicken — saves $2.40/plate at current prices" = 90
- THRESHOLD: score must be >= 70 to pass

## Test 3: Show Your Work (Cross-Signal Reasoning)
"Does this insight connect multiple data sources, or is it just restating one number?"
- Score 0-100 where HIGHER = BETTER REASONING (good)
- "BLS says dairy is up" = 20 (just repeating one source)
- "BLS dairy +12% + OSM shows 3 new competitors + rising 'meal prep' searches = shift to value positioning" = 85
- THRESHOLD: score must be >= 60 to pass

## PULSE OUTPUT TO EVALUATE:
{pulse_text}

## RULES:
- Evaluate EVERY insight in the output
- For each insight, provide all three scores and a verdict: PASS, REWRITE, or DROP
- If verdict is REWRITE, provide SPECIFIC rewrite_instruction explaining what to fix
- Set overall_pass = true ONLY if ALL insights pass ALL three tests
- Be harsh but fair — the goal is to make insights genuinely useful

Return ONLY the structured JSON matching the CritiqueResult schema."""


# ---------------------------------------------------------------------------
# Critique agent (LLM — scores the insights)
# ---------------------------------------------------------------------------

PulseCritiqueAgent = LlmAgent(
    name="PulseCritique",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.MEDIUM,
    description="Evaluates pulse insights for obviousness, actionability, and cross-signal reasoning.",
    instruction=_critique_instruction,
    output_key="critiqueResult",
    output_schema=CritiqueResult,
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# CritiqueRouter — deterministic BaseAgent (no LLM, no tokens)
#
# Reads critiqueResult from state. If overall_pass → escalate to exit loop.
# Otherwise, builds rewriteFeedback string and writes it to state so the
# next agent in the sequence (WeeklyPulseAgent) can revise.
# ---------------------------------------------------------------------------


class CritiqueRouter(BaseAgent):
    """Deterministic post-critique router — zero LLM calls.

    On pass  → sets escalate=True on the yielded Event, which causes the
               LoopAgent to break before the rewrite agent runs.
    On fail  → writes rewriteFeedback to session.state and yields a
               normal Event so the loop continues to the rewrite agent.
    """

    name: str = "CritiqueRouter"
    description: str = "Routes critique result: escalate on pass, write feedback on fail."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        critique_raw = state.get("critiqueResult", "")

        # Parse critique result (may be str from output_key or dict)
        if isinstance(critique_raw, str):
            try:
                critique = json.loads(critique_raw)
            except (json.JSONDecodeError, ValueError):
                critique = {}
        elif isinstance(critique_raw, dict):
            critique = critique_raw
        else:
            critique = {}

        overall_pass = critique.get("overall_pass", False)
        insights = critique.get("insights", [])

        if overall_pass:
            logger.info("[CritiqueRouter] All insights passed — escalating to exit loop")
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                actions=EventActions(escalate=True, state_delta={"rewriteFeedback": ""}),
            )
            return

        # Build rewrite feedback for failing insights
        feedback_parts: list[str] = []
        for ic in insights:
            verdict = ic.get("verdict", "PASS")
            if verdict in ("REWRITE", "DROP"):
                rank = ic.get("insight_rank", "?")
                obv = ic.get("obviousness_score", 0)
                act = ic.get("actionability_score", 0)
                cross = ic.get("cross_signal_score", 0)
                instruction = ic.get("rewrite_instruction", "Improve quality")
                feedback_parts.append(
                    f"Insight #{rank}: {verdict} — obviousness={obv}, "
                    f"actionability={act}, cross_signal={cross}. "
                    f"Feedback: {instruction}"
                )

        rewrite_feedback = "\n".join(feedback_parts) if feedback_parts else "Some insights need improvement."

        logger.info(
            f"[CritiqueRouter] {len(feedback_parts)} insights need rewrite — "
            f"continuing loop"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"rewriteFeedback": rewrite_feedback}),
        )


# ---------------------------------------------------------------------------
# Import the synthesis agent for rewrite iterations
# ---------------------------------------------------------------------------

from hephae_agents.research.weekly_pulse_agent import WeeklyPulseAgent  # noqa: E402


# ---------------------------------------------------------------------------
# Stage 4: Critique Loop
# ---------------------------------------------------------------------------

_critique_then_rewrite = SequentialAgent(
    name="CritiqueThenRewrite",
    sub_agents=[PulseCritiqueAgent, CritiqueRouter(), WeeklyPulseAgent],
)

critique_loop = LoopAgent(
    name="CritiqueLoop",
    sub_agents=[_critique_then_rewrite],
    max_iterations=2,
)
