"""Personalized AI tool recommendation engine.

Scores tools against a business profile using rule-based signals:
1. Profile gaps — missing website, menu, social, POS
2. Analysis results — low SEO score, high food cost, no online ordering
3. Business category — fine dining vs pizza vs food truck
4. Location context — income level, competition density, area type

Usage:
    from hephae_common.tool_recommender import recommend_tools

    picks = recommend_tools(
        tools=all_tools,                # from ai_tools collection
        business_profile=profile,       # from locatedBusiness + analysis data
        max_results=5,
    )
    # Returns: [{"tool": {...}, "score": 0.92, "reason": "You don't have...", "priority": "high"}]
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Signal extractors ─────────────────────────────────────────────────────

def _extract_gaps(profile: dict[str, Any]) -> dict[str, bool]:
    """Detect what's missing from the business profile."""
    return {
        "no_website": not profile.get("officialUrl"),
        "no_menu": not profile.get("menuUrl"),
        "no_social": not (profile.get("socialLinks") and any(profile["socialLinks"].values())),
        "no_delivery": not profile.get("deliveryLinks"),
        "no_pos": not profile.get("posSystem"),
        "no_booking": not profile.get("bookingUrl"),
        "no_reviews_strategy": not profile.get("reviewPlatforms"),
    }


def _extract_analysis_signals(profile: dict[str, Any]) -> dict[str, Any]:
    """Extract signals from completed analyses."""
    analyses = profile.get("analyses", {})
    return {
        "seo_score": analyses.get("seo", {}).get("overallScore"),
        "margin_score": analyses.get("margin", {}).get("overall_score"),
        "has_seo": bool(analyses.get("seo")),
        "has_margin": bool(analyses.get("margin")),
        "has_traffic": bool(analyses.get("traffic")),
        "has_competitive": bool(analyses.get("competitive")),
        "menu_not_found": profile.get("profileFindings", {}).get("noMenuOnline", False),
    }


def _extract_category_signals(profile: dict[str, Any]) -> dict[str, str]:
    """Infer business sub-category."""
    name = (profile.get("name") or "").lower()
    persona = (profile.get("persona") or "").lower()
    category = (profile.get("category") or profile.get("businessType") or "").lower()
    combined = f"{name} {persona} {category}"

    sub_category = "general"
    if any(x in combined for x in ["fine dining", "upscale", "prix fixe", "tasting"]):
        sub_category = "fine_dining"
    elif any(x in combined for x in ["pizza", "pizzeria"]):
        sub_category = "pizza"
    elif any(x in combined for x in ["food truck", "cart", "mobile"]):
        sub_category = "food_truck"
    elif any(x in combined for x in ["bakery", "bake", "pastry", "donut"]):
        sub_category = "bakery"
    elif any(x in combined for x in ["cafe", "coffee", "espresso"]):
        sub_category = "cafe"
    elif any(x in combined for x in ["bar ", "pub ", "brewery", "cocktail"]):
        sub_category = "bar"
    elif any(x in combined for x in ["fast", "quick service", "counter"]):
        sub_category = "fast_casual"

    return {"sub_category": sub_category, "raw_category": category}


def _extract_location_signals(profile: dict[str, Any]) -> dict[str, Any]:
    """Extract location-based signals."""
    local = profile.get("localIntel", {})
    stats = profile.get("stats", {})
    return {
        "spending_power": (local.get("spendingPower") or "").lower(),
        "price_sensitivity": (local.get("priceSensitivity") or "").lower(),
        "competitor_count": stats.get("competitorCount", 0),
        "median_income": stats.get("medianIncome"),
    }


# ── Scoring rules ─────────────────────────────────────────────────────────

def _score_tool(
    tool: dict[str, Any],
    gaps: dict[str, bool],
    analysis: dict[str, Any],
    category: dict[str, str],
    location: dict[str, Any],
    feedback: dict[str, float],
) -> tuple[float, str, str]:
    """Score a single tool against the business profile.

    Returns: (score 0-1, reason string, priority level)
    """
    score = 0.0
    reasons: list[str] = []
    tool_name = (tool.get("toolName") or "").lower()
    capability = (tool.get("aiCapability") or tool.get("description") or "").lower()
    cat = (tool.get("technologyCategory") or "").lower()

    # ── Gap-based scoring (highest weight) ─────────────────────────
    if gaps["no_website"] and any(x in capability for x in ["website", "seo", "web build", "online presence"]):
        score += 0.3
        reasons.append("You don't have a website — this helps build one")
    if gaps["no_menu"] and any(x in capability for x in ["menu", "food cost", "recipe", "pricing"]):
        score += 0.3
        reasons.append("No menu URL found — this helps get your menu online")
    if gaps["no_social"] and any(x in capability for x in ["social media", "instagram", "facebook", "post", "caption"]):
        score += 0.25
        reasons.append("No social media presence detected")
    if gaps["no_delivery"] and any(x in capability for x in ["ordering", "delivery", "doordash"]):
        score += 0.2
        reasons.append("No delivery platforms — this adds online ordering")
    if gaps["no_reviews_strategy"] and any(x in capability for x in ["review", "reputation", "feedback"]):
        score += 0.2
        reasons.append("No review management — this automates review collection")
    if gaps["no_pos"] and any(x in capability for x in ["pos", "point of sale", "payment"]):
        score += 0.15
        reasons.append("No POS system detected")

    # ── Analysis-based scoring ─────────────────────────────────────
    seo_score = analysis.get("seo_score")
    if seo_score is not None and seo_score < 50 and any(x in capability for x in ["seo", "google", "search", "visibility"]):
        score += 0.25
        reasons.append(f"Your SEO score is {seo_score}/100 — this helps improve it")

    margin_score = analysis.get("margin_score")
    if margin_score is not None and margin_score < 60 and any(x in capability for x in ["cost", "margin", "inventory", "waste", "pricing"]):
        score += 0.25
        reasons.append(f"Margin score {margin_score}/100 — this helps reduce food costs")

    if analysis.get("menu_not_found") and any(x in capability for x in ["menu", "food photo", "menu builder"]):
        score += 0.2
        reasons.append("Your menu isn't discoverable online — critical gap")

    # ── Category matching ──────────────────────────────────────────
    sub = category.get("sub_category", "")
    if sub == "bakery" and any(x in capability for x in ["bakery", "ingredient", "recipe", "waste"]):
        score += 0.1
    elif sub == "pizza" and any(x in capability for x in ["ordering", "delivery", "phone order"]):
        score += 0.1
    elif sub == "fine_dining" and any(x in capability for x in ["reservation", "booking", "wine", "sommelier"]):
        score += 0.1
    elif sub == "food_truck" and any(x in capability for x in ["mobile", "location", "schedule", "route"]):
        score += 0.1
    elif sub == "bar" and any(x in capability for x in ["inventory", "pour", "cocktail", "bar"]):
        score += 0.1

    # ── Location context ───────────────────────────────────────────
    if location.get("spending_power") == "high" and "premium" in capability:
        score += 0.05
    if location.get("competitor_count", 0) > 10 and any(x in capability for x in ["competitive", "reputation", "review"]):
        score += 0.1
        reasons.append(f"{location['competitor_count']} competitors nearby — reputation matters")

    # ── Free tool bonus ────────────────────────────────────────────
    if tool.get("isFree"):
        score += 0.1
        reasons.append("Free to start")

    # ── GenAI DIY bonus (higher emphasis per user preference) ──────
    if any(x in cat for x in ["general purpose", "gpt store", "gemini", "emerging"]):
        score += 0.15  # Boost GenAI tools
    if any(x in tool_name for x in ["gemini", "gpt", "chatgpt", "ai studio"]):
        score += 0.1

    # ── Feedback adjustment ────────────────────────────────────────
    tool_id = tool.get("toolId") or tool.get("id", "")
    fb = feedback.get(tool_id, 0)
    score += fb * 0.2  # +0.2 for thumbs up, -0.2 for thumbs down

    # ── Reputation tier ────────────────────────────────────────────
    tier = (tool.get("reputationTier") or "").upper()
    if tier == "ESTABLISHED":
        score += 0.05

    # Normalize to 0-1
    score = min(1.0, max(0.0, score))

    # Priority level
    priority = "high" if score >= 0.4 else "medium" if score >= 0.2 else "low"

    reason = reasons[0] if reasons else "Relevant for your business type"
    return score, reason, priority


# ── Public API ────────────────────────────────────────────────────────────

def recommend_tools(
    tools: list[dict[str, Any]],
    business_profile: dict[str, Any],
    feedback: dict[str, float] | None = None,
    max_results: int = 5,
    min_score: float = 0.1,
) -> list[dict[str, Any]]:
    """Score and rank AI tools for a specific business.

    Args:
        tools: Full list of AI tools (from ai_tools collection)
        business_profile: Business data including identity, analyses, localIntel
        feedback: Optional dict of tool_id → score (-1 to 1) from user feedback
        max_results: Max tools to return
        min_score: Minimum score threshold

    Returns list of dicts: {"tool": {...}, "score": float, "reason": str, "priority": str}
    """
    gaps = _extract_gaps(business_profile)
    analysis = _extract_analysis_signals(business_profile)
    category = _extract_category_signals(business_profile)
    location = _extract_location_signals(business_profile)
    fb = feedback or {}

    scored: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for tool in tools:
        name = (tool.get("toolName") or "").lower()
        if name in seen_names:
            continue
        seen_names.add(name)

        score, reason, priority = _score_tool(tool, gaps, analysis, category, location, fb)
        if score >= min_score:
            scored.append({
                "tool": tool,
                "score": round(score, 3),
                "reason": reason,
                "priority": priority,
            })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_results]


def build_recommendation_context(
    recommendations: list[dict[str, Any]],
) -> str:
    """Format recommendations as a string for chatbot context injection."""
    if not recommendations:
        return ""

    lines = ["Personalized Tool Recommendations (based on this business's profile):"]
    for i, rec in enumerate(recommendations[:5], 1):
        t = rec["tool"]
        name = t.get("toolName", "?")
        reason = rec["reason"]
        price = t.get("pricing", "")
        free = " [FREE]" if t.get("isFree") else ""
        lines.append(f"  {i}. {name}{free} — {reason}")
        if price:
            lines.append(f"     Pricing: {price[:60]}")
    return "\n".join(lines)
