"""AI Tools Digest ADK agents — synthesize the full AI tools catalog into two categories:

1. **Enterprise Platforms** — established software (Toast, Square, Birdeye, ServiceTitan)
   that require sales calls, contracts, and integration. These are "buy" decisions.

2. **GenAI DIY Tools** — new-age tools built on Gemini, GPT, Claude that a business owner
   can start using in minutes. Custom GPTs, AI Studio apps, free prompts. These are
   "build/try" decisions with near-zero cost.

Pipeline: AiToolsDataLoader → AiToolsSynthesizer (LlmAgent) → AiToolsDigestAssembler
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

# Categories that are "enterprise" — require sales, contracts, integration
ENTERPRISE_CATEGORIES = {"POS Integration", "Platform Feature", "Standalone SaaS"}
# Categories that are GenAI DIY — free/cheap, instant start, AI-native
GENAI_CATEGORIES = {"General Purpose AI", "GPT Store", "Gemini AI Studio", "Emerging"}
# Keywords in tool names/descriptions that signal GenAI DIY
GENAI_KEYWORDS = ["gemini", "gpt", "chatgpt", "claude", "ai studio", "prompt", "custom gpt", "gem"]


def _classify_tool(tool: dict) -> str:
    """Classify a tool as 'enterprise' or 'genai'."""
    cat = (tool.get("technologyCategory") or "").strip()
    name = (tool.get("toolName") or "").lower()
    desc = (tool.get("description") or tool.get("aiCapability") or "").lower()
    vendor = (tool.get("vendor") or "").lower()

    # Explicit GenAI markers
    if cat in GENAI_CATEGORIES:
        return "genai"
    if any(kw in name or kw in desc or kw in vendor for kw in GENAI_KEYWORDS):
        return "genai"
    # Free + low pricing signals GenAI DIY
    if tool.get("isFree") and ("free" in (tool.get("pricing") or "").lower()):
        pricing = (tool.get("pricing") or "").lower()
        if any(x in pricing for x in ["$0", "free plan", "free tier", "free basic"]):
            # But not enterprise tools with free tiers (e.g., Homebase free for 1 location)
            if not any(x in name for x in ["toast", "square", "clover", "lightspeed", "yelp", "servicetitan"]):
                return "genai"
    return "enterprise"


class AiToolsDataLoader(BaseAgent):
    """Load and classify all AI tools for a vertical."""

    name: str = "AiToolsDataLoader"
    description: str = "Loads and classifies AI tools into enterprise vs GenAI categories."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        vertical = state.get("vertical", "")
        week_of = state.get("weekOf", "")

        logger.info(f"[AiToolsDigest] Loading tools for {vertical} ({week_of})")

        from hephae_db.firestore.ai_tools import get_tools_for_vertical
        all_tools = await get_tools_for_vertical(vertical, limit=60)

        from hephae_db.firestore.tech_intelligence import get_tech_intelligence
        tech_intel = await get_tech_intelligence(vertical, week_of)
        if not tech_intel:
            from datetime import datetime, timedelta
            d = datetime.utcnow() - timedelta(days=7)
            tech_intel = await get_tech_intelligence(vertical, f"{d.year}-W{d.isocalendar()[1]:02d}")

        # Classify
        enterprise_tools = []
        genai_tools = []
        for t in all_tools:
            if _classify_tool(t) == "genai":
                genai_tools.append(t)
            else:
                enterprise_tools.append(t)

        # Sub-classify enterprise by function
        enterprise_by_function: dict[str, list] = {}
        for t in enterprise_tools:
            func = _infer_function(t)
            enterprise_by_function.setdefault(func, []).append(t)

        # Sub-classify genai by capability
        genai_by_type: dict[str, list] = {}
        for t in genai_tools:
            gtype = _infer_genai_type(t)
            genai_by_type.setdefault(gtype, []).append(t)

        logger.info(
            f"[AiToolsDigest] {len(enterprise_tools)} enterprise, {len(genai_tools)} genai, "
            f"tech_intel={'yes' if tech_intel else 'no'}"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={
                "enterpriseTools": enterprise_tools,
                "genaiTools": genai_tools,
                "enterpriseByFunction": {k: v[:5] for k, v in enterprise_by_function.items()},
                "genaiByType": {k: v[:5] for k, v in genai_by_type.items()},
                "rawTechIntel": tech_intel or {},
                "totalTools": len(all_tools),
            }),
        )


def _infer_function(tool: dict) -> str:
    """Infer the business function of an enterprise tool."""
    name = (tool.get("toolName") or "").lower()
    cap = (tool.get("aiCapability") or tool.get("description") or "").lower()
    if any(x in name or x in cap for x in ["pos", "toast", "square", "clover", "lightspeed", "order"]):
        return "POS & Ordering"
    if any(x in name or x in cap for x in ["review", "reputation", "birdeye", "podium", "yelp"]):
        return "Reviews & Reputation"
    if any(x in name or x in cap for x in ["schedul", "shift", "labor", "workforce", "7shift", "lineup", "homebase"]):
        return "Scheduling & Labor"
    if any(x in name or x in cap for x in ["inventory", "cost", "margin", "invoice", "market man", "wisk"]):
        return "Inventory & Costs"
    if any(x in name or x in cap for x in ["market", "social", "email", "sms", "campaign", "ad "]):
        return "Marketing & CRM"
    if any(x in name or x in cap for x in ["book", "reserv", "appointment", "opentable"]):
        return "Booking & Reservations"
    if any(x in name or x in cap for x in ["account", "tax", "payroll", "expense", "bookkeep"]):
        return "Accounting & Finance"
    if any(x in name or x in cap for x in ["phone", "call", "voice", "chat", "receptionist"]):
        return "Phone & Communications"
    return "Operations"


def _infer_genai_type(tool: dict) -> str:
    """Infer the GenAI tool type."""
    name = (tool.get("toolName") or "").lower()
    cat = (tool.get("technologyCategory") or "").lower()
    cap = (tool.get("aiCapability") or tool.get("description") or "").lower()
    if "gemini" in name or "ai studio" in name or "gemini" in cat:
        return "Gemini Apps & Prompts"
    if "gpt" in name or "chatgpt" in name or "gpt store" in cat:
        return "Custom GPTs"
    if any(x in cap for x in ["photo", "image", "video", "visual", "design"]):
        return "Visual AI"
    if any(x in cap for x in ["voice", "call", "phone"]):
        return "Voice AI"
    if any(x in cap for x in ["automat", "workflow", "zapier", "agent"]):
        return "AI Automation"
    if any(x in cap for x in ["writing", "content", "copy", "caption", "social"]):
        return "Content Generation"
    return "AI Utilities"


AI_TOOLS_SYNTH_INSTRUCTION = """You are an AI tools analyst writing a tools landscape digest for the {vertical} industry.
Your digest must clearly separate two categories:

**CATEGORY 1: Enterprise Platforms** — established software requiring evaluation, contracts, integration.
These are "buy" decisions. Focus on: which is the market leader per function, what's their latest AI update,
and what's the realistic monthly cost.

**CATEGORY 2: GenAI DIY Tools** — new-age tools built on Gemini, ChatGPT, Claude that an owner can
start using TODAY with near-zero cost. Custom GPTs, AI Studio apps, free prompts, workflow automations.
THIS IS THE HIGH-EMPHASIS SECTION. Business owners want to know: "What can I do RIGHT NOW for free?"

Given the data below, write:

1. **enterpriseLandscape** (1-2 paragraphs): Quick overview of the enterprise platform leaders
   per function (POS, reviews, scheduling, etc.). Focus on latest AI features and realistic costs.

2. **genaiLandscape** (2-3 paragraphs): DETAILED overview of the GenAI DIY opportunity.
   What can an owner build with Gemini AI Studio? Which custom GPTs are most valuable?
   What free tools deliver the most impact? Be very specific — name exact tools, prompts, use cases.
   This is what excites a business owner who hasn't tried AI yet.

3. **genaiQuickWins** (5-7 items): Specific things an owner can do THIS WEEK with free GenAI tools.
   Each should take < 30 minutes and deliver visible results. Include the tool name and exact steps.

4. **enterpriseTopPicks** (3-5): Best enterprise platform per major function with pricing.

5. **freeStack**: The recommended zero-cost starting combination (3-4 tools).

Return as JSON: {{"enterpriseLandscape": "...", "genaiLandscape": "...", "genaiQuickWins": ["..."], "enterpriseTopPicks": [{{"tool": "...", "function": "...", "pricing": "...", "aiFeature": "..."}}], "freeStack": [{{"tool": "...", "capability": "...", "url": "..."}}]}}
"""


def _ai_tools_synth_before_model(callback_context: Any, llm_request: Any) -> None:
    state = callback_context.state
    enterprise = state.get("enterpriseByFunction", {})
    genai = state.get("genaiByType", {})
    tech = state.get("rawTechIntel", {})
    vertical = state.get("vertical", "unknown")
    total = state.get("totalTools", 0)

    parts = [f"Vertical: {vertical} | Total tools: {total}"]

    # Enterprise tools by function
    parts.append("\n== ENTERPRISE PLATFORMS ==")
    for func, tools in enterprise.items():
        lines = []
        for t in tools[:4]:
            price = t.get('pricing', '?')[:50]
            lines.append(f"  {t.get('toolName', '?')} — {t.get('aiCapability', '')[:80]} [{price}]")
        parts.append(f"\n[{func}] ({len(tools)})\n" + "\n".join(lines))

    # GenAI tools by type
    parts.append("\n\n== GENAI DIY TOOLS ==")
    for gtype, tools in genai.items():
        lines = []
        for t in tools[:5]:
            url = t.get('url', '')
            lines.append(f"  {t.get('toolName', '?')} — {t.get('aiCapability', '')[:80]}")
            if url: lines[-1] += f" ({url})"
            if t.get('isFree'): lines[-1] += " [FREE]"
        parts.append(f"\n[{gtype}] ({len(tools)})\n" + "\n".join(lines))

    # Tech intel platform landscape
    if tech.get("platforms"):
        parts.append("\n\n== PLATFORM INTELLIGENCE ==")
        for cat, info in tech["platforms"].items():
            if isinstance(info, dict):
                parts.append(f"  {cat}: leader={info.get('leader', '?')} — update: {info.get('recentUpdate', '?')[:80]}")

    context = "\n".join(parts)
    instruction = AI_TOOLS_SYNTH_INSTRUCTION.replace("{vertical}", vertical)
    llm_request.config = llm_request.config or genai_types.GenerateContentConfig()
    llm_request.config.system_instruction = instruction
    llm_request.contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=context)])
    )


class AiToolsDigestAssembler(BaseAgent):
    name: str = "AiToolsDigestAssembler"
    description: str = "Assembles the final AI tools digest with enterprise vs GenAI split."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        synth_raw = state.get("synthOutput", "")
        enterprise_tools = state.get("enterpriseTools", [])
        genai_tools = state.get("genaiTools", [])
        tech = state.get("rawTechIntel", {})

        import re
        enterprise_landscape = ""
        genai_landscape = ""
        genai_quick_wins: list[str] = []
        enterprise_top_picks: list[dict] = []
        free_stack: list[dict] = []

        try:
            json_match = re.search(r'\{[\s\S]*\}', synth_raw)
            if json_match:
                parsed = json.loads(json_match.group())
                enterprise_landscape = parsed.get("enterpriseLandscape", "")
                genai_landscape = parsed.get("genaiLandscape", synth_raw)
                genai_quick_wins = parsed.get("genaiQuickWins", [])
                enterprise_top_picks = parsed.get("enterpriseTopPicks", [])
                free_stack = parsed.get("freeStack", [])
            else:
                genai_landscape = synth_raw
        except (json.JSONDecodeError, AttributeError):
            genai_landscape = synth_raw

        digest = {
            # Two-category structure
            "enterpriseLandscape": enterprise_landscape,
            "genaiLandscape": genai_landscape,
            "genaiQuickWins": genai_quick_wins[:7],
            "enterpriseTopPicks": enterprise_top_picks[:5],
            "freeStack": free_stack[:4],

            # Counts
            "totalTools": state.get("totalTools", 0),
            "enterpriseCount": len(enterprise_tools),
            "genaiCount": len(genai_tools),

            # Raw categories for UI
            "enterpriseByFunction": state.get("enterpriseByFunction", {}),
            "genaiByType": state.get("genaiByType", {}),

            # Platform intel
            "platformUpdates": tech.get("platforms", {}),
            "techHighlight": tech.get("weeklyHighlight"),
            "sourceTechIntelId": tech.get("id"),
        }

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"aiToolsDigest": digest}),
        )


def create_ai_tools_digest_agent() -> SequentialAgent:
    return SequentialAgent(
        name="AiToolsDigestPipeline",
        sub_agents=[
            AiToolsDataLoader(),
            LlmAgent(
                name="AiToolsSynthesizer",
                model=AgentModels.PRIMARY_MODEL,
                instruction=AI_TOOLS_SYNTH_INSTRUCTION,
                before_model_callback=_ai_tools_synth_before_model,
                output_key="synthOutput",
                on_model_error_callback=fallback_on_error,
            ),
            AiToolsDigestAssembler(),
        ],
    )
