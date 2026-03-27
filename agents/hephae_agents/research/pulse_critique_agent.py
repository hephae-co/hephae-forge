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

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types as genai_types

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_db.schemas import CritiqueResult

logger = logging.getLogger(__name__)


# Static critique instruction — cacheable across zip codes
CRITIQUE_INSTRUCTION = """You are a business owner reviewing an intelligence briefing someone wrote for you. You paid good money for this and you're pissed if it's vague.

## Pass A: Local Briefing Quality
Check the localBriefing section:
- thisWeekInTown: Are events specific? Must have venue name + date. Score 0-100 (higher = better). THRESHOLD: >= 50 if local data exists in the reports.
- competitorWatch: Are businesses NAMED? (not "local competitors"). THRESHOLD: >= 50 if competitor data exists.
- communityBuzz: Based on actual social data? (not generic filler). THRESHOLD: >= 40.
- If the Local Scout Report or Social Pulse contains specific events/businesses but localBriefing is empty, set overall_pass = false with instruction to populate it.

Include a "local_briefing_score" (0-100) in your output. If < 50 and local data was available, set overall_pass = false and local_briefing_pass = false.

## Pass B: Insight Quality
Score each insight on THREE tests. Be brutal — flowery business-school language is an automatic fail.

## Test 1: "Do I Already Know This?" (Obviousness)
Score 0-100, HIGHER = MORE OBVIOUS = WORSE.
- "There's a local event this weekend" = 95 (I live here, I know)
- "Food costs are rising" = 80 (I buy food every day, I know)
- "BLS dairy index hit 283.4, up 12.1% YoY vs poultry down 5.3%" = 10 (I don't track BLS)
- THRESHOLD: must be BELOW 30 to pass

## Test 2: "What Exactly Do I Do Monday Morning?" (Actionability)
Score 0-100, HIGHER = MORE ACTIONABLE = BETTER.
- "Consider diversifying revenue streams" = 5 (means nothing)
- "Monitor the competitive landscape" = 10 (still means nothing)
- "Capitalize on emerging trends" = 5 (consultant nonsense)
- "Add a $12.99 family pickup deal on DoorDash this week" = 90 (I can do that Monday)
- "Replace cream pasta special with grilled chicken, saves $1.40/plate" = 85 (specific, actionable)
- AUTOMATIC FAIL if insight uses: "consider", "monitor", "capitalize", "leverage", "stay informed", "be aware", "proactive approach", "strategic positioning"
- THRESHOLD: must be 70 OR ABOVE to pass

## Test 3: "Where Are the Numbers?" (Data Density)
Score 0-100, HIGHER = MORE DATA = BETTER.
- "Costs are rising and competition is increasing" = 5 (zero numbers)
- "BLS shows dairy up 12%" = 30 (one number, one source)
- "Dairy +12.1% YoY (BLS), 10 competitors in 1500m (OSM), median income $95K (Census) — premium pricing viable but watch food cost on cream-heavy items" = 85 (three sources, three numbers, specific conclusion)
- THRESHOLD: must be 60 OR ABOVE to pass
- Count the actual numbers in the analysis. If fewer than 2, score cannot exceed 40.

## SCORING RULES:
- Evaluate EVERY insight
- Verdict: PASS (all 3 tests pass), REWRITE (fixable), or DROP (unfixable fluff)
- For REWRITE: give SPECIFIC instructions like "Add the actual BLS dairy index number and the OSM competitor count. Replace 'consider adjusting' with a specific menu item swap and dollar savings."
- overall_pass = true ONLY if every insight passes all 3 tests
- If an insight has zero specific numbers from the data → automatic DROP
- If an insight reads like a business school essay → automatic REWRITE with instruction to strip the fluff

The pulse output to evaluate and cross-check data will be provided in the data context below.

Return ONLY the structured JSON matching the CritiqueResult schema."""


def _critique_before_model(ctx, llm_request):
    """Inject pulse output and cross-check data into the model request."""
    state = ctx.state
    pulse_output = state.get("pulseOutput", "")

    pulse_text = ""
    if pulse_output:
        if isinstance(pulse_output, str):
            pulse_text = pulse_output
        else:
            pulse_text = json.dumps(pulse_output, default=str, indent=2)

    sections = []

    # Industry-specific persona context
    industry_cfg = state.get("industryConfig", {})
    persona = industry_cfg.get("critiquePersona", "restaurant owner with 15 years experience")
    sections.append(f"CRITIQUE PERSONA: {persona}")

    sections.append(f"\n## PULSE OUTPUT TO EVALUATE:\n{pulse_text}")

    local_report = state.get("localReport", "")
    social_pulse = state.get("socialPulse", "")
    if local_report:
        lr = local_report if isinstance(local_report, str) else json.dumps(local_report, default=str)
        sections.append(f"\n=== LOCAL SCOUT REPORT (for cross-check) ===\n{lr[:2000]}")
    if social_pulse:
        sp = social_pulse if isinstance(social_pulse, str) else json.dumps(social_pulse, default=str)
        sections.append(f"\n=== SOCIAL PULSE (for cross-check) ===\n{sp[:2000]}")

    context_text = "\n".join(sections)
    llm_request.contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=context_text)])
    )
    return None


# Keep backward compat export
_critique_instruction = CRITIQUE_INSTRUCTION


# ---------------------------------------------------------------------------
# Critique agent (LLM — scores the insights) — static instruction for caching
# ---------------------------------------------------------------------------

PulseCritiqueAgent = LlmAgent(
    name="PulseCritique",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.MEDIUM,
    description="Evaluates pulse insights for obviousness, actionability, and cross-signal reasoning.",
    instruction=CRITIQUE_INSTRUCTION,
    before_model_callback=_critique_before_model,
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

        # If ALL failing insights are close to passing (actionability > 62, cross_signal > 55),
        # escalate to avoid a DEEP rewrite for marginal improvements
        if not overall_pass and insights:
            failing = [ic for ic in insights if ic.get("verdict") in ("REWRITE", "DROP")]
            if failing and all(
                ic.get("actionability_score", 0) >= 62 and ic.get("cross_signal_score", 0) >= 55
                for ic in failing
            ):
                logger.info("[CritiqueRouter] Failing insights are close to threshold — escalating to avoid unnecessary rewrite")
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


