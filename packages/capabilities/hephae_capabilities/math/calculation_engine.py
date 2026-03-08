"""
Deterministic margin math — no LLM.
Exact port of CalculationEngine from src/agents/margin-analyzer/surgeon.ts.

RULE: All arithmetic for "Annual Profit Leakage" and "Margin %" happens here,
never in a prompt.
"""

from __future__ import annotations

from typing import Any


def calculate_leakage(
    item: dict[str, Any],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate the absolute optimal price and identify revenue leakage for a menu item.

    Args:
        item: MenuItem dict with item_name, current_price, category, description?
        competitors: list of CompetitorPrice dicts
        commodities: list of CommodityTrend dicts

    Returns:
        MenuAnalysisItem dict with all original fields plus analysis results
    """
    item_name: str = item.get("item_name", "")
    current_price: float = float(item.get("current_price", 0))
    category: str = item.get("category", "")

    # 1. Calculate Neighborhood Median
    exact_matches = [c for c in competitors if c.get("item_match") == item_name]
    if exact_matches:
        prices = sorted(c.get("price", 0) for c in exact_matches)
        median_price = prices[len(prices) // 2]
    else:
        median_price = current_price  # Fallback if no competitor data

    # 2. Calculate Commodity Trend Impact
    max_inflation = 0.0
    for c in commodities:
        ingredient = c.get("ingredient", "")
        inflation = c.get("inflation_rate_12mo", 0)
        if (
            ingredient.lower() in item_name.lower()
            or (ingredient == "Eggs" and "breakfast" in category.lower())
        ):
            if inflation > max_inflation:
                max_inflation = inflation

    # Inflation Factor: If inflation is 20%, factor is 1.20
    commodity_factor = 1 + (max_inflation / 100)
    inflationary_price = current_price * commodity_factor

    # 3. Formula: Max(Price * Commodity_Trend, Neighborhood_Median)
    target_base = max(inflationary_price, median_price)

    # Add a small "Surgical Margin" (5%) for safety/profit
    recommended_price = round(target_base * 1.05, 2)

    leakage = max(0.0, recommended_price - current_price)

    rationale = f"Competitors average ${median_price}. Key ingredients inflated by {max_inflation}%."

    return {
        **item,
        "competitor_benchmark": median_price,
        "commodity_factor": max_inflation,
        "recommended_price": recommended_price,
        "price_leakage": round(leakage, 2),
        "confidence_score": 90 if exact_matches else 50,
        "rationale": rationale,
    }


def perform_margin_surgery(
    items: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Batch calculation across all menu items."""
    return [calculate_leakage(item, competitors, commodities) for item in items]
