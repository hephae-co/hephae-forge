"""QualityGateAgent — decides whether a discovered business is worth processing.

This is the critical filter between discovery and capability analysis.
It runs as an ADK LlmAgent using the PRIMARY (cheapest) model.

Disqualifies a business if:
  - No reachable contact (no phone, email, OR website)
  - Chain / national franchise detected (McDonald's, Starbucks, etc.)
  - Business appears permanently closed
  - Profile is too thin to generate useful insights

Only businesses that pass this gate have all capability agents run on them.
This is both a quality control mechanism AND the primary cost control lever —
we spend compute only on businesses we can actually help.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai.types import Content, Part

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)

_QUALITY_GATE_INSTRUCTION = """You are a business quality screener for Hephae, a platform that provides
AI-powered intelligence reports for independent local businesses.

Your job is to evaluate a discovered business profile and decide whether it should
receive a full suite of analysis reports (SEO audit, competitive analysis, margin surgery,
social media audit, traffic forecast).

Call qualify(qualified, reason) with your decision.

DISQUALIFY (qualified=false) if ANY of the following are true:
1. CHAIN OR FRANCHISE: The business is a national or regional chain, franchise, or corporate-owned
   location. Examples: McDonald's, Burger King, Subway, Starbucks, Dunkin', Domino's, Pizza Hut,
   Chipotle, Panera, Chick-fil-A, Wendy's, Taco Bell, KFC, Popeyes, Shake Shack, Five Guys,
   Jersey Mike's, Wawa, 7-Eleven, CVS, Walgreens, Walmart, Target, Home Depot, Best Buy,
   Marriott, Hilton, Holiday Inn, Anytime Fitness, Planet Fitness, H&R Block, Edward Jones,
   State Farm, Allstate, or any other recognizable chain. These businesses do not need our help.
   Banks: Chase, Wells Fargo, Bank of America, Citibank, TD Bank, Capital One, PNC, US Bank, etc.
   Dollar stores: Dollar Tree, Dollar General, Family Dollar, Five Below, etc.

2. NO REACHABLE CONTACT: The profile contains NO phone number AND NO email AND NO website URL.
   We cannot deliver value to a business we cannot reach.

3. PERMANENTLY CLOSED: The profile indicates the business is closed, out of business,
   or no longer operating.

4. INSUFFICIENT DATA: The profile is so thin (just a name and address, nothing else) that
   running analysis would produce only hallucinated results.

QUALIFY (qualified=true) if:
- The business appears to be an independently owned local business
- It has at least one contact point (phone, email, or website)
- There is enough profile data to generate meaningful analysis

Be decisive. When in doubt about whether something is a chain, disqualify it.
Independent franchisees of large chains (e.g., a local McDonald's owner) are still
disqualified — we focus on truly independent operators.
"""


def _make_qualify_tool(result_container: list) -> FunctionTool:
    """Create a qualify() tool that captures the agent's decision."""

    def qualify(qualified: bool, reason: str) -> str:
        """Record the quality gate decision for this business.

        Args:
            qualified: True if the business should receive full analysis. False to skip.
            reason: A brief explanation of the decision (1-2 sentences).
        """
        result_container.append({"qualified": qualified, "reason": reason})
        return "Decision recorded."

    return FunctionTool(func=qualify)


def _build_profile_summary(identity: dict[str, Any]) -> str:
    """Build a concise profile string for the agent to evaluate."""
    parts = []

    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    parts.append(f"Business Name: {name}")
    if address:
        parts.append(f"Address: {address}")

    category = identity.get("category", "")
    if category:
        parts.append(f"Category: {category}")

    phone = identity.get("phone", "")
    email = identity.get("email", "")
    url = identity.get("officialUrl", "")
    if phone:
        parts.append(f"Phone: {phone}")
    if email:
        parts.append(f"Email: {email}")
    if url:
        parts.append(f"Website: {url}")

    social = identity.get("socialLinks") or {}
    active_social = {k: v for k, v in social.items() if v}
    if active_social:
        parts.append(f"Social: {', '.join(active_social.keys())}")

    description = identity.get("description", "") or identity.get("persona", "")
    if description:
        parts.append(f"Description: {description[:300]}")

    hours = identity.get("hours", "")
    if hours:
        parts.append(f"Hours: {str(hours)[:100]}")

    news = identity.get("news", [])
    if news and isinstance(news, list):
        parts.append(f"Recent news items: {len(news)}")

    return "\n".join(parts)


async def run_quality_gate(identity: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a business profile through the quality gate.

    Returns:
        {"qualified": bool, "reason": str}
        On agent failure, defaults to qualified=True (fail-open to avoid data loss).
    """
    result_container: list[dict] = []
    qualify_tool = _make_qualify_tool(result_container)

    agent = LlmAgent(
        name="QualityGateAgent",
        model=AgentModels.PRIMARY_MODEL,
        instruction=_QUALITY_GATE_INSTRUCTION,
        tools=[qualify_tool],
        on_model_error_callback=fallback_on_error,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="hephae-hub",
        agent=agent,
        session_service=session_service,
    )

    session_id = f"qg-{int(time.time() * 1000)}"
    await session_service.create_session(
        app_name="hephae-hub", user_id="batch", session_id=session_id, state={}
    )

    profile_text = _build_profile_summary(identity)
    prompt = f"Evaluate this business profile:\n\n{profile_text}"

    try:
        async for _ in runner.run_async(
            user_id="batch",
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            pass
    except Exception as e:
        logger.warning(
            f"[QualityGate] Agent error for {identity.get('name')}: {e} — defaulting to qualified=True"
        )
        return {"qualified": True, "reason": "Quality gate failed — defaulting to qualified"}

    if not result_container:
        logger.warning(
            f"[QualityGate] No decision recorded for {identity.get('name')} — defaulting to qualified=True"
        )
        return {"qualified": True, "reason": "No decision — defaulting to qualified"}

    return result_container[0]
