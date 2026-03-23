"""TechScout — ADK agent tree for technology intelligence per vertical.

Architecture:
  create_tech_scout() -> SequentialAgent:
    Stage 1: PlatformMonitor (ParallelAgent)
      - BookingScout, POSScout, MarketingScout, AIToolScout, CommunityScout
    Stage 2: TechSynthesizer (LlmAgent)
      - Merges findings into structured TechProfile

Runs weekly (Sunday), produces tech_intelligence Firestore docs consumed
by both industry pulse and zipcode pulse pipelines.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-vertical platform knowledge (used to build targeted search queries)
# ---------------------------------------------------------------------------

VERTICAL_PLATFORMS: dict[str, dict[str, list[str]]] = {
    "restaurant": {
        "booking": ["OpenTable", "Resy", "Tock", "Yelp Reservations", "Seated"],
        "pos": ["Toast", "Square for Restaurants", "Clover", "Lightspeed", "SpotOn"],
        "ordering": ["DoorDash Merchant", "ChowNow", "BentoBox", "Olo", "Ordermark", "Cuboh"],
        "operations": ["MarketMan", "BlueCart", "Restaurant365", "7shifts", "Homebase"],
        "marketing": ["Popmenu", "Podium", "Birdeye", "Mailchimp", "Yelp for Business"],
    },
    "bakery": {
        "ordering": ["Square Online", "Toast", "Shopify POS", "BentoBox", "ChowNow"],
        "pos": ["Square", "Toast", "Clover", "Lightspeed"],
        "operations": ["CostBrain", "FlexiBake", "MarketMan", "RecipeCost", "MenuCalc"],
        "marketing": ["Mailchimp", "Instagram Shopping", "Canva", "Later"],
        "wholesale": ["BlueCart", "FoodServiceDirect", "Cut+Dry"],
    },
    "barber": {
        "booking": ["SQUIRE", "Booksy", "Vagaro", "Boulevard", "Fresha", "GlossGenius"],
        "pos": ["Square", "Clover", "SQUIRE Pay", "Stripe Terminal"],
        "operations": ["DaySmart Salon", "Rosy Salon Software", "Phorest"],
        "marketing": ["Podium", "Birdeye", "Mailchimp", "Canva"],
        "education": ["Barber Blueprint", "BarbersConnect", "National Barber Board"],
    },
}

VERTICAL_SUBREDDITS: dict[str, list[str]] = {
    "restaurant": ["restaurantowners", "restaurant", "KitchenConfidential"],
    "bakery": ["Baking", "cakedecorating", "Breadit"],
    "barber": ["Barber", "Barbershop"],
}


# ---------------------------------------------------------------------------
# Scout instruction builders
# ---------------------------------------------------------------------------

def _build_scout_instruction(vertical: str, category: str, platforms: list[str]) -> str:
    """Build instruction for a category-specific tech scout."""
    platform_list = ", ".join(platforms) if platforms else "general tools"
    subreddits = VERTICAL_SUBREDDITS.get(vertical, ["smallbusiness"])
    reddit_str = ", ".join(f"r/{s}" for s in subreddits)

    return f"""You are a Technology Scout for {vertical} businesses, specializing in {category} tools.

Search for the LATEST news, updates, and launches in the {category} space for {vertical} businesses.

Known platforms in this space: {platform_list}

Search strategies (use google_search for each):
1. Each known platform: "[platform] new features 2026" or "[platform] update March 2026"
2. Vertical-specific: "{vertical} {category} software new 2026"
3. AI angle: "{vertical} {category} AI automation 2026"
4. Community: "site:reddit.com {reddit_str} {category} software recommendation"
5. Comparison: "best {category} software for {vertical} small business 2026"

For each relevant finding, include:
- Platform/tool name
- What's new or notable (be specific — feature names, pricing changes, launch dates)
- Why it matters to a {vertical} owner (time saved, revenue impact, cost reduction)
- Source URL

Focus on findings from the LAST 30 DAYS. Skip generic "AI is transforming everything" articles.
Prioritize: actual product launches > feature updates > pricing changes > trend reports.

Return your findings as a structured summary. Include at least 2-3 specific, verified findings."""


SYNTHESIZER_INSTRUCTION = """You are a Technology Advisor for small businesses. You've received research from 5 technology scouts.

Synthesize ALL findings into a structured TechProfile.

Return a JSON object with EXACTLY these fields:

{
  "platforms": {
    "booking": {"leader": "name", "alternatives": ["..."], "recentUpdate": "specific update or null", "trend": "one-line trend"},
    "pos": {"leader": "name", "alternatives": ["..."], "recentUpdate": "...", "trend": "..."},
    "ordering": {"leader": "name", "alternatives": ["..."], "recentUpdate": "...", "trend": "..."},
    "operations": {"leader": "name", "alternatives": ["..."], "recentUpdate": "...", "trend": "..."},
    "marketing": {"leader": "name", "alternatives": ["..."], "recentUpdate": "...", "trend": "..."}
  },
  "aiOpportunities": [
    {
      "tool": "specific tool name",
      "capability": "what it does specifically",
      "relevance": "HIGH or MEDIUM",
      "actionForOwner": "What should the owner DO? Be specific — 'enable X in settings' or 'sign up for free trial at...'"
    }
  ],
  "communityRecommendations": [
    {
      "source": "reddit or forum name",
      "tool": "what's recommended",
      "context": "why they recommend it"
    }
  ],
  "emergingTrends": [
    {
      "trend": "specific trend name",
      "evidence": "what makes you say this (cite sources)",
      "timeframe": "now or 3months or 6months"
    }
  ],
  "weeklyHighlight": {
    "title": "The ONE most impactful finding this week",
    "detail": "Why it matters — with specific numbers if available",
    "action": "Exactly what a business owner should do about it this week"
  }
}

Rules:
- ONLY include verified findings from the scout reports — do NOT hallucinate tools or features
- If scouts found nothing new for a category, set recentUpdate to null
- weeklyHighlight should be the single most actionable finding
- aiOpportunities: only include tools that are ACTUALLY AVAILABLE (not upcoming/rumored)
- Be specific: "SQUIRE launched AI no-show prediction" not "AI is changing scheduling"

Output JSON only — no markdown fencing."""


# ---------------------------------------------------------------------------
# Factory function (fresh agents per invocation — ADK parent rule)
# ---------------------------------------------------------------------------

def create_tech_scout(vertical: str) -> SequentialAgent:
    """Create a fresh TechScout agent tree for a specific vertical."""

    platforms = VERTICAL_PLATFORMS.get(vertical, VERTICAL_PLATFORMS["restaurant"])

    # Stage 1: Category-specific scouts (parallel)
    scouts = []
    for category, platform_list in platforms.items():
        scout = LlmAgent(
            name=f"TechScout_{category}",
            model=AgentModels.PRIMARY_MODEL,
            description=f"Scouts {category} technology for {vertical} businesses.",
            instruction=_build_scout_instruction(vertical, category, platform_list),
            tools=[google_search],
            output_key=f"techFindings_{category}",
            on_model_error_callback=fallback_on_error,
        )
        scouts.append(scout)

    platform_monitor = ParallelAgent(
        name="PlatformMonitor",
        description=f"Parallel technology scouts for {vertical}.",
        sub_agents=scouts,
    )

    # Stage 2: Synthesizer
    def _synth_instruction(ctx) -> str:
        state = getattr(ctx, "state", {})
        v = state.get("vertical", vertical)
        return f"You are analyzing technology for the {v} industry.\n\n{SYNTHESIZER_INSTRUCTION}"

    synthesizer = LlmAgent(
        name="TechSynthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes tech scout findings into a TechProfile.",
        instruction=_synth_instruction,
        output_key="techProfile",
        on_model_error_callback=fallback_on_error,
    )

    return SequentialAgent(
        name=f"TechScout_{vertical}",
        description=f"Technology intelligence pipeline for {vertical}.",
        sub_agents=[platform_monitor, synthesizer],
    )
