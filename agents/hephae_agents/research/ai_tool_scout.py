"""AiToolScout — ADK agent tree for discovering AI tools relevant to a vertical.

Architecture:
  create_ai_tool_scout(vertical) -> SequentialAgent:
    Stage 1: AiToolCategoryScouts (ParallelAgent)
      - One LlmAgent per AI tool category (automation, marketing, operations, etc.)
    Stage 2: AiToolSynthesizer (LlmAgent)
      - Merges findings into structured AiToolProfile JSON

Focuses on tools useful to non-tech small business owners.
Prioritizes: free tools > cheap tools > established tools > new tools.
Filters out developer tools, APIs, SDKs, and enterprise-only products.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI tool categories to scout per vertical
# All 19 registered industries covered — no fallback to restaurant defaults
# ---------------------------------------------------------------------------

VERTICAL_AI_CATEGORIES: dict[str, list[str]] = {
    # Food & Beverage
    "restaurant":    ["pos_and_ordering", "marketing_and_reviews", "operations_and_scheduling", "customer_communication", "menu_and_pricing"],
    "bakery":        ["ordering_and_ecommerce", "marketing_and_social", "inventory_and_costing", "customer_communication", "pos"],
    "coffee_shop":   ["pos_and_ordering", "loyalty_and_crm", "marketing_and_social", "inventory_management", "customer_communication"],
    "pizza":         ["online_ordering", "delivery_management", "marketing_and_reviews", "pos_and_ordering", "customer_communication"],
    "food_truck":    ["mobile_ordering", "social_media_content", "route_and_event_planning", "marketing_and_reviews", "pos"],

    # Beauty & Personal Care
    "barber":        ["booking_and_appointments", "marketing_and_reviews", "client_management", "pos", "social_media_content"],
    "hair_salon":    ["booking_and_appointments", "client_management", "marketing_and_social", "pos", "social_media_content"],
    "nail_salon":    ["booking_and_appointments", "client_management", "marketing_and_reviews", "social_media_content", "pos"],
    "spa_massage":   ["booking_and_appointments", "client_retention", "marketing_and_social", "intake_and_waivers", "pos"],
    "tattoo_studio": ["booking_and_appointments", "portfolio_and_marketing", "client_consultation", "social_media_content", "waivers_and_aftercare"],

    # Health & Wellness
    "gym_fitness":   ["member_management", "class_scheduling", "marketing_and_social", "billing_and_memberships", "client_retention"],
    "yoga_pilates":  ["class_scheduling", "member_management", "marketing_and_social", "payment_and_memberships", "content_creation"],
    "dental":        ["appointment_management", "patient_communication", "billing_and_insurance", "review_management", "patient_intake"],

    # Home & Trade Services
    "auto_repair":   ["job_estimating", "appointment_scheduling", "customer_communication", "marketing_and_reviews", "parts_and_inventory"],
    "residential_cleaning": ["job_scheduling", "client_communication", "quote_and_estimating", "marketing_and_reviews", "staff_management"],
    "plumbing_hvac": ["job_estimating", "dispatch_and_scheduling", "customer_communication", "marketing_and_reviews", "invoice_and_billing"],

    # Retail & Specialty
    "florist":       ["ordering_and_ecommerce", "event_management", "marketing_and_social", "inventory_management", "customer_communication"],
    "dry_cleaner":   ["customer_tracking", "order_management", "marketing_and_reviews", "pos", "customer_communication"],
    "pet_grooming":  ["booking_and_appointments", "client_management", "marketing_and_reviews", "social_media_content", "pos"],
}


# ---------------------------------------------------------------------------
# Synthesizer instruction — blocks generic tools, requires vertical-specific finds
# ---------------------------------------------------------------------------

SYNTHESIZER_INSTRUCTION = """You are an AI Tools Analyst for non-technical small business owners.

You have received research from multiple scouts about AI-powered tools for a specific business vertical.

Your job: synthesize ALL findings into a structured AiToolProfile with the MOST SPECIFIC and ACTIONABLE tools for this exact vertical.

Return a JSON object with EXACTLY these fields:

{
  "tools": [
    {
      "toolName": "exact product name (e.g., Toast AI, Vagaro AI, Boulevard AI, GlossGenius)",
      "vendor": "company or creator name",
      "category": "pos_and_ordering|booking_and_appointments|marketing_and_reviews|operations_and_scheduling|customer_communication|menu_and_pricing|social_media_content|inventory_and_costing|client_management|billing_and_memberships|class_scheduling|job_estimating|general_smb",
      "description": "one sentence: what it does specifically for THIS vertical's owner",
      "pricing": "specific pricing string, e.g. 'Free' or '$29/mo' or 'Free with ChatGPT Plus ($20/mo)' — never null",
      "isFree": true or false,
      "freeAlternativeTo": "name of paid tool this replaces, or null",
      "url": "canonical product URL or GPT Store link",
      "aiCapability": "what the AI specifically does — be concrete, e.g. 'auto-drafts responses to negative reviews in your brand voice'",
      "relevanceScore": "HIGH|MEDIUM|LOW",
      "reputationTier": "established|emerging|unknown",
      "isNew": true or false (launched or had a major AI update in the last 60 days),
      "sourceUrl": "URL where this tool was found",
      "actionForOwner": "one concrete action: e.g. 'Sign up free at vagaro.com/ai' — not 'explore this tool'"
    }
  ],
  "weeklyHighlight": {
    "title": "The single most important AI tool finding this week — one sentence naming the specific tool",
    "detail": "Why it matters to THIS vertical's owner — specific with numbers if available (time saved, cost saved, revenue impact)",
    "action": "Exactly what the business owner should do THIS WEEK — a URL or specific step"
  }
}

CRITICAL RULES:
- Include 6-12 tools total — quality over quantity
- ONLY tools available and usable RIGHT NOW — no rumors, betas requiring waitlists, or vaporware
- NO developer tools: no APIs, SDKs, Python libraries, LangChain, vector databases, fine-tuning services
- NO enterprise-only products that require a sales call or have no public pricing
- isFree = true only if the tool is usable at zero cost (free GPT, free tier, no credit card required)
- freeAlternativeTo: if this free tool replaces a paid product owners currently pay for, name it
- relevanceScore HIGH = saves the owner >2h/week OR >$100/mo OR directly eliminates a major pain point
- reputationTier "established" = 1000+ users/conversations OR from a well-known brand OR 500+ ProductHunt upvotes
- actionForOwner must be specific: "Sign up at X" or "Search for 'Y' in ChatGPT's GPT Store" — never generic

EXCLUSION RULES — do NOT include these as standalone tools unless there is a SPECIFIC published GPT or app for this vertical:
- ChatGPT / GPT-4 / GPT-4o (too generic — every owner already knows about it)
- Claude / Anthropic (too generic)
- Google Gemini / Bard (too generic)
- Microsoft Copilot (too generic)
- Midjourney / DALL-E / Stable Diffusion (image-only, not business tools)
Exception: if there is a NAMED GPT in the GPT Store specifically for this vertical (e.g., "Restaurant Menu GPT" with 1000+ conversations), include it with the exact GPT Store URL.

SPECIFICITY RULE: At least 4 of the tools must be PURPOSE-BUILT for this vertical (e.g., Toast for restaurants, Vagaro for salons, ServiceTitan for HVAC) — not generic SMB tools. Generic tools (Canva, Mailchimp, HubSpot) may be included only if they have launched a SPECIFIC AI feature for this vertical recently.

isNew = true if the tool launched OR had a major AI feature update in the last 60 days. If scouts found Product Hunt launches or recent press coverage, use that as evidence.

Output JSON only — no markdown fencing, no explanation."""


def _build_scout_instruction(vertical: str, category: str) -> str:
    """Build instruction for a category-specific AI tool scout."""
    category_readable = category.replace("_", " ")
    return f"""You are an AI Tool Scout for {vertical} small businesses, finding tools in the "{category_readable}" category.

Search for AI-powered tools that a NON-TECHNICAL {vertical} owner can use TODAY — no coding, no setup complexity.
Focus on: vertical-specific software with AI features, free GPTs built for {vertical}, no-code AI tools purpose-built for {vertical}.

Run google_search for ALL of these queries in order:
1. "AI tool {category_readable} {vertical} 2026"
2. "{vertical} software AI feature {category_readable} new 2025 OR 2026"
3. "site:producthunt.com {vertical} {category_readable} AI"
4. "best {category_readable} software {vertical} AI automated"
5. "{vertical} {category_readable} app AI launched 2026"
6. "{category_readable} AI {vertical} owner free OR affordable"

For each AI tool found, extract:
- Exact tool/product name and vendor
- Is it PURPOSE-BUILT for {vertical}? (preferred) or generic SMB?
- Whether it is FREE or has a free tier
- Specific AI capability (not "uses AI" — be concrete: e.g., "auto-generates appointment reminders from booking history")
- Pricing (exact — "Free", "$19/mo", "Free tier up to 50 clients")
- The product URL
- Whether it launched or had a major AI update in the last 60 days (check ProductHunt date, press releases, blog posts)
- One concrete action a {vertical} owner can take today

IMPORTANT: Do NOT include ChatGPT, Claude, Gemini, or Copilot as generic tools.
Only include them if you find a SPECIFIC named GPT in the ChatGPT GPT Store for {vertical} {category_readable} with a direct link.

Return a structured summary of 2-4 tools per category, prioritizing vertical-specific tools over generic ones."""


# ---------------------------------------------------------------------------
# Factory function (fresh agents per invocation — ADK parent rule)
# ---------------------------------------------------------------------------

def create_ai_tool_scout(vertical: str) -> SequentialAgent:
    """Create a fresh AiToolScout agent tree for a specific vertical.

    Must be called fresh per invocation — ADK agents cannot be reused
    once attached to a parent (raises "already has a parent" error).
    """
    categories = VERTICAL_AI_CATEGORIES.get(vertical)
    if categories is None:
        logger.warning(f"[AiToolScout] No categories defined for vertical '{vertical}' — using restaurant fallback")
        categories = VERTICAL_AI_CATEGORIES["restaurant"]

    # Stage 1: Parallel category scouts
    scouts = []
    for category in categories:
        scout = LlmAgent(
            name=f"AiToolScout_{category}",
            model=AgentModels.PRIMARY_MODEL,
            description=f"Scouts AI tools in the '{category}' category for {vertical} businesses.",
            instruction=_build_scout_instruction(vertical, category),
            tools=[google_search],
            output_key=f"aiToolFindings_{category}",
            on_model_error_callback=fallback_on_error,
        )
        scouts.append(scout)

    category_scouts = ParallelAgent(
        name="AiToolCategoryScouts",
        description=f"Parallel AI tool scouts for {vertical}.",
        sub_agents=scouts,
    )

    # Stage 2: Synthesizer
    def _synth_instruction(ctx) -> str:
        state = getattr(ctx, "state", {})
        v = state.get("vertical", vertical)
        return f"You are analyzing AI tools for the {v} industry.\n\n{SYNTHESIZER_INSTRUCTION}"

    synthesizer = LlmAgent(
        name="AiToolSynthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes AI tool scout findings into a structured AiToolProfile.",
        instruction=_synth_instruction,
        output_key="aiToolProfile",
        on_model_error_callback=fallback_on_error,
    )

    return SequentialAgent(
        name=f"AiToolScout_{vertical}",
        description=f"AI tool discovery pipeline for {vertical}.",
        sub_agents=[category_scouts, synthesizer],
    )
