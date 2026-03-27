"""
Deterministic margin math — no LLM.

RULE: All arithmetic for food cost %, annual leakage, and recommended pricing
happens here, never in a prompt.

Industry standard food cost benchmarks:
  < 25%  — excellent (fine dining where labor covers the gap)
  25-30% — good      (healthy QSR / casual target)
  30-35% — fair      (acceptable but watch margins)
  35-40% — poor      (pricing is too low or COGS too high)
  > 40%  — critical  (every plate sold at this item is a loss)

Recommended pricing targets 30% food cost (industry sweet spot for
casual/neighbourhood restaurants) adjusted upward to the competitor median
if the market supports it.
"""

from __future__ import annotations

from typing import Any

# Target food cost ratio — 30% is industry standard for casual restaurants.
# Items above TARGET_FOOD_COST_PCT are flagged as underpriced.
TARGET_FOOD_COST_PCT = 30.0

# Typical restaurant food cost as a fraction of menu price
# (used to back-calculate estimated COGS from current price)
TYPICAL_FOOD_COST_FRACTION = 0.32


def _food_cost_label(pct: float) -> str:
    if pct < 25:
        return "excellent"
    if pct < 30:
        return "good"
    if pct < 35:
        return "fair"
    if pct < 40:
        return "poor"
    return "critical"


def calculate_leakage(
    item: dict[str, Any],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate food cost %, recommended price, and annual leakage for a menu item.

    Primary metric: food_cost_pct (industry standard).
    Secondary metric: price_leakage ($/week opportunity if repriced).
    """
    item_name: str = item.get("item_name", "")
    current_price: float = float(item.get("current_price") or 0)
    category: str = item.get("category", "")

    if current_price <= 0:
        return {**item, "food_cost_pct": None, "food_cost_label": "unknown",
                "recommended_price": None, "price_leakage": 0, "confidence_score": 0,
                "rationale": "Price not available."}

    # 1. Competitor median price
    exact_matches = [c for c in competitors if c.get("item_match") == item_name]
    if exact_matches:
        prices = sorted(float(c.get("price", current_price)) for c in exact_matches)
        competitor_median = prices[len(prices) // 2]
        benchmark_source = exact_matches[0].get("confidence", "competitor")
    else:
        competitor_median = current_price
        benchmark_source = "no_data"

    # 2. Estimated COGS — uses commodity inflation to adjust the typical fraction
    # The upstream Watchdog agent identifies ALL relevant commodities for the full menu.
    # Strategy: use the weighted average of ALL commodity trends (not just string-matched ones),
    # giving more weight to directly-name-matched commodities.
    max_inflation = 0.0
    matched_commodity = ""
    all_inflations = []

    for c in commodities:
        ingredient = (c.get("ingredient") or "").lower()
        inflation = float(c.get("inflation_rate_12mo") or 0)
        item_lc = item_name.lower()
        cat_lc = category.lower()

        all_inflations.append(inflation)

        # Direct name match gets priority (2× weight — handled by max)
        if ingredient and (ingredient in item_lc or ingredient in cat_lc):
            if inflation > max_inflation:
                max_inflation = inflation
                matched_commodity = c.get("ingredient", "")

    # If no direct match found, use weighted-average of all commodity trends
    # (all commodities were inferred from the full menu, so they're all relevant)
    if max_inflation == 0.0 and all_inflations:
        avg_inflation = sum(all_inflations) / len(all_inflations)
        max_inflation = avg_inflation
        matched_commodity = "mixed inputs"

    # Adjust COGS fraction upward for inflation pressure
    inflation_adj = max_inflation / 100.0
    effective_food_cost_fraction = TYPICAL_FOOD_COST_FRACTION + (inflation_adj * 0.5)
    estimated_cogs = round(current_price * effective_food_cost_fraction, 2)

    # 3. Food cost % = COGS / sale_price * 100
    food_cost_pct = round((estimated_cogs / current_price) * 100, 1)
    food_cost_label = _food_cost_label(food_cost_pct)

    # 4. Recommended price — target 30% food cost, capped at competitor median + 10%
    # Formula: price_for_target = COGS / TARGET_FOOD_COST_PCT
    price_for_target_margin = round(estimated_cogs / (TARGET_FOOD_COST_PCT / 100.0), 2)

    # Don't price above competitor median + 10% (market ceiling)
    market_ceiling = round(competitor_median * 1.10, 2)
    recommended_price = min(price_for_target_margin, market_ceiling)
    recommended_price = max(recommended_price, current_price)  # never recommend lower
    recommended_price = round(recommended_price, 2)

    # 5. Leakage = opportunity per order ($/plate)
    leakage_per_plate = max(0.0, recommended_price - current_price)

    # 6. Build rationale string
    commodity_note = f" {matched_commodity} up {max_inflation:.1f}% YoY." if matched_commodity and max_inflation > 1 else ""
    if benchmark_source == "web_search":
        bench_note = f"Competitors (web) avg ${competitor_median:.2f}."
    elif benchmark_source == "cuisine_estimate":
        bench_note = f"Area average estimated at ${competitor_median:.2f}."
    else:
        bench_note = "No competitor data — using market ceiling estimate."

    rationale = (
        f"Estimated food cost: {food_cost_pct}% ({food_cost_label}). "
        f"{bench_note}"
        f"{commodity_note}"
    )

    return {
        **item,
        # Primary metric
        "food_cost_pct": food_cost_pct,
        "food_cost_label": food_cost_label,
        "estimated_cogs": estimated_cogs,
        # Pricing
        "competitor_benchmark": competitor_median,
        "recommended_price": recommended_price,
        "price_leakage": round(leakage_per_plate, 2),
        # Metadata
        "commodity_factor": max_inflation,
        "matched_commodity": matched_commodity,
        "confidence_score": 85 if exact_matches else (60 if benchmark_source == "cuisine_estimate" else 40),
        "rationale": rationale,
    }


def perform_margin_surgery(
    items: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Batch calculation across all menu items. Returns sorted by food_cost_pct desc."""
    results = [calculate_leakage(item, competitors, commodities) for item in items]
    return sorted(results, key=lambda x: float(x.get("food_cost_pct") or 0), reverse=True)
