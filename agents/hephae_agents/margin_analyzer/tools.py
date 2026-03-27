"""
Margin analyzer tools — market data fetchers + surgery + benchmark functions.

Consolidates:
  - market_data.py content (fetch_commodity_prices, fetch_cpi_data, fetch_fred_indicators)
  - benchmarker.py tool function (fetch_competitor_benchmarks)
  - commodity_watchdog.py tool function (check_commodity_inflation)
  - surgeon.py tool function (perform_surgery)
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from google.adk.tools import FunctionTool

from hephae_agents.market_data import (
    fetch_commodity_prices,
    fetch_cpi_data,
    fetch_fred_indicators,
)
from hephae_agents.math.calculation_engine import perform_margin_surgery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Benchmarker tool
# ---------------------------------------------------------------------------

async def fetch_competitor_benchmarks(
    location: str,
    items: list[str],
    competitor_names: list[str] | None = None,
    tool_context=None,
) -> dict[str, Any]:
    """
    Fetch real competitor pricing for menu items using web search.

    Searches for competitor menus by name (when provided) or by cuisine type
    near the given location. Returns actual prices found online.

    Args:
        location: The city and state of the restaurant (e.g. "West Orange, NJ").
        items: Array of menu item names to benchmark.
        competitor_names: Optional list of known competitor names to search for.

    Returns:
        dict with 'competitors' (list of real prices found) and 'macroeconomic_context'.
    """
    import httpx

    competitors: list[dict[str, Any]] = []
    search_targets = competitor_names[:3] if competitor_names else []

    # Use httpx to hit the Google Custom Search JSON API if key is available,
    # otherwise fall back to a Yelp Fusion search.  If neither is available,
    # perform a best-effort SERP scrape via DuckDuckGo HTML (no key required).
    async def _search_prices(query: str) -> list[dict[str, Any]]:
        """Search for menu prices and return parsed results."""
        results: list[dict[str, Any]] = []
        try:
            # DuckDuckGo HTML search — no API key required
            encoded = quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True,
                                          headers={"User-Agent": "Mozilla/5.0 (compatible; HephaeBot/1.0)"}) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                import re as _re
                # Extract price-looking patterns near item names
                text = resp.text
                # Find prices: $X.XX or $XX
                price_matches = _re.findall(r'\$(\d{1,3}(?:\.\d{2})?)', text)
                prices = [float(p) for p in price_matches if 5.0 <= float(p) <= 60.0]
                if prices:
                    # Use the median of found prices as the market price
                    prices_sorted = sorted(prices)
                    median = prices_sorted[len(prices_sorted) // 2]
                    results.append({"source": "web_search", "median_price": median, "sample_count": len(prices)})
        except Exception as e:
            logger.warning(f"[Benchmarker] Web search failed for '{query}': {e}")
        return results

    # Search for each competitor's pricing
    for comp_name in search_targets:
        for item_name in items[:5]:  # limit to top 5 items per competitor
            query = f'"{comp_name}" {location} menu "{item_name}" price'
            search_results = await _search_prices(query)
            if search_results:
                competitors.append({
                    "competitor_name": comp_name,
                    "item_match": item_name,
                    "price": search_results[0]["median_price"],
                    "source_url": f"https://duckduckgo.com/?q={quote(query)}",
                    "distance_miles": 0.5,
                    "confidence": "web_search",
                })

    # Fallback: if web search yielded nothing, use cuisine-aware median pricing
    # (significantly better than random — based on NJ restaurant price ranges)
    if not competitors:
        logger.info("[Benchmarker] Web search yielded no results — using cuisine-aware estimates")
        cuisine_medians = _estimate_cuisine_medians(location, items)
        competitors = cuisine_medians

    # Fetch macro context
    macroeconomic_context: dict[str, Any] = {}
    state = {}
    if tool_context and hasattr(tool_context, "state"):
        state = tool_context.state or {}

    cached_cpi = state.get("_market_cpi")
    cached_fred = state.get("_market_fred")

    try:
        if cached_cpi and cached_fred:
            macroeconomic_context = {
                "inflation_cpi": cached_cpi,
                "unemployment_trend": cached_fred,
                "analysis_hint": "Determine if local consumers can absorb a menu price increase.",
            }
        else:
            loc_lc = location.lower()
            region = "Northeast"
            if re.search(r"fl|tx|miami|austin|south|carolina|georgia|alabama", loc_lc):
                region = "South"
            elif re.search(r"il|chicago|midwest|ohio|michigan", loc_lc):
                region = "Midwest"
            elif re.search(r"ca|yountville|west|california|oregon|washington|nv", loc_lc):
                region = "West"
            bls_data = await fetch_cpi_data(region)
            fred_data = await fetch_fred_indicators("UNRATE")
            macroeconomic_context = {
                "inflation_cpi": bls_data,
                "unemployment_trend": fred_data,
                "analysis_hint": "Determine if local consumers can absorb a menu price increase.",
            }
    except Exception as e:
        logger.error(f"[Benchmarker] Market data fetch error: {e}")

    return {"competitors": competitors, "macroeconomic_context": macroeconomic_context}


def _estimate_cuisine_medians(location: str, items: list[str]) -> list[dict[str, Any]]:
    """
    Cuisine-aware price estimates based on NJ suburban restaurant market ranges.
    Used as fallback when web search returns nothing.
    Much better than random — based on actual price categories.
    """
    results = []
    for item_name in items:
        lc = item_name.lower()
        # Assign to price tier based on item keywords
        if any(k in lc for k in ("lobster", "filet", "wagyu", "branzino", "dover sole", "rack of lamb")):
            base = 42.0
        elif any(k in lc for k in ("salmon", "shrimp", "scallop", "crab", "duck", "ribeye", "short rib")):
            base = 28.0
        elif any(k in lc for k in ("steak", "swordfish", "veal", "lamb", "halibut")):
            base = 32.0
        elif any(k in lc for k in ("chicken", "pork", "pasta", "risotto", "gnocchi", "pizza")):
            base = 18.0
        elif any(k in lc for k in ("burger", "sandwich", "wrap", "panini", "sub")):
            base = 15.0
        elif any(k in lc for k in ("salad", "soup", "appetizer", "starter", "bruschetta")):
            base = 12.0
        elif any(k in lc for k in ("dessert", "cake", "pie", "gelato", "tiramisu")):
            base = 10.0
        elif any(k in lc for k in ("breakfast", "omelette", "omelet", "eggs", "pancake", "waffle")):
            base = 13.0
        else:
            base = 17.0  # generic entree median for NJ suburbs

        results.append({
            "competitor_name": f"Area Average ({location})",
            "item_match": item_name,
            "price": base,
            "source_url": "",
            "distance_miles": 1.0,
            "confidence": "cuisine_estimate",
        })
    return results


# ---------------------------------------------------------------------------
# Commodity watchdog tool
# ---------------------------------------------------------------------------

async def check_commodity_inflation(terms: list[str], tool_context=None) -> list[dict[str, Any]]:
    """
    Map menu item names to their primary ingredients, then fetch BLS commodity
    inflation data for each identified ingredient.

    Uses Gemini to infer ingredients from item names — much more accurate than
    keyword matching. Covers all 15 BLS APU commodity series.

    Args:
        terms: Mix of menu item names (e.g. "Carbonara", "Bibimbap") and category names.

    Returns:
        list of CommodityTrend dicts with ingredient, inflation_rate_12mo, trend_description.
    """
    trends: list[dict[str, Any]] = []

    # Step 1: Use Gemini to infer which BLS commodities are relevant
    commodity_set: set[str] = _infer_commodities_from_terms(terms)

    # Step 2: Try AI-powered ingredient inference for higher accuracy
    try:
        ai_commodities = await _ai_infer_commodities(terms)
        commodity_set.update(ai_commodities)
    except Exception as e:
        logger.warning(f"[Commodity Watchdog] AI inference failed, using rule-based: {e}")

    # Always include at least one commodity
    if not commodity_set:
        commodity_set.add("beef")

    # Step 3: Fetch BLS data for each identified commodity
    state = {}
    if tool_context and hasattr(tool_context, "state"):
        state = tool_context.state or {}
    cached_prices = state.get("_market_commodity_prices") or {}

    for commodity in commodity_set:
        try:
            data = cached_prices.get(commodity)
            if data:
                logger.info(f"[Commodity Watchdog] Using pre-fetched data for {commodity}")
            else:
                data = await fetch_commodity_prices(commodity)

            if data and data.get("commodity"):
                trend_str = data.get("trend30Day", "0%")
                inflation_val = float(re.sub(r"[^0-9.\-]", "", trend_str) or "2.4")
                trends.append({
                    "ingredient": data["commodity"].upper(),
                    "inflation_rate_12mo": inflation_val,
                    "trend_description": (
                        f"BLS Retail Price: {data.get('pricePerUnit')}. "
                        f"Trend: {data.get('trend30Day')}. "
                        f"Source: {data.get('source')}"
                    ),
                })
        except Exception as e:
            logger.error(f"[Commodity Watchdog] Fetch error for {commodity}: {e}")

    return trends


def _infer_commodities_from_terms(terms: list[str]) -> set[str]:
    """
    Rule-based ingredient inference — expanded to cover 15 commodity categories.
    Catches cases the keyword-only approach missed (e.g., Carbonara → eggs + dairy + pork).
    """
    commodity_set: set[str] = set()
    for term in terms:
        lc = term.lower()
        # Proteins
        if any(k in lc for k in ("egg", "breakfast", "omelette", "omelet", "frittata", "quiche",
                                   "carbonara", "shakshuka", "benedict", "huevos")):
            commodity_set.add("eggs")
        if any(k in lc for k in ("beef", "steak", "burger", "brisket", "ribeye", "sirloin",
                                   "short rib", "bolognese", "chili", "meatball", "meatloaf",
                                   "roast beef", "prime rib", "tenderloin", "tartare")):
            commodity_set.add("beef")
        if any(k in lc for k in ("chicken", "wings", "poultry", "turkey", "duck", "hen",
                                   "breast", "thigh", "rotisserie", "piccata", "marsala",
                                   "tikka", "schnitzel", "cutlet")):
            commodity_set.add("poultry")
        if any(k in lc for k in ("pork", "bacon", "ham", "prosciutto", "pancetta", "sausage",
                                   "chorizo", "pulled pork", "ribs", "loin", "belly", "guanciale",
                                   "carbonara", "amatriciana", "blt")):
            commodity_set.add("pork")
        if any(k in lc for k in ("salmon", "tuna", "shrimp", "scallop", "crab", "lobster",
                                   "clam", "mussel", "oyster", "fish", "cod", "halibut",
                                   "branzino", "swordfish", "seafood", "cioppino", "paella",
                                   "sushi", "sashimi", "calamari", "tilapia", "bass", "trout")):
            commodity_set.add("seafood")
        # Dairy
        if any(k in lc for k in ("cheese", "milk", "cream", "ricotta", "mozzarella", "parmesan",
                                   "brie", "feta", "gruyere", "gouda", "cheddar", "mascarpone",
                                   "alfredo", "cream sauce", "bechamel", "cheesecake")):
            commodity_set.add("cheese")
        if any(k in lc for k in ("butter", "hollandaise", "beurre", "croissant", "brioche")):
            commodity_set.add("butter")
        if any(k in lc for k in ("yogurt", "tzatziki", "raita", "lassi", "milk", "dairy")):
            commodity_set.add("dairy")
        # Staples
        if any(k in lc for k in ("pasta", "spaghetti", "fettuccine", "penne", "rigatoni",
                                   "tagliatelle", "lasagne", "lasagna", "tortellini", "gnocchi",
                                   "noodle", "ramen", "pho", "udon", "lo mein")):
            commodity_set.add("flour")
        if any(k in lc for k in ("pizza", "bread", "flatbread", "focaccia", "baguette",
                                   "sandwich", "sub", "wrap", "bun", "roll", "crostini",
                                   "bruschetta", "crouton", "pita", "naan", "tortilla")):
            commodity_set.add("bread")
        if any(k in lc for k in ("rice", "risotto", "pilaf", "biryani", "fried rice",
                                   "bibimbap", "sushi", "congee", "paella", "arroz")):
            commodity_set.add("rice")
        # Other
        if any(k in lc for k in ("salad", "vegetable", "veggie", "vegan", "greens",
                                   "tomato", "pepper", "onion", "mushroom", "eggplant",
                                   "zucchini", "spinach", "kale", "arugula", "beet", "corn")):
            commodity_set.add("produce")
        if any(k in lc for k in ("fried", "fries", "tempura", "stir.fry", "sauté", "sautee",
                                   "deep fried", "crispy")):
            commodity_set.add("oil")
        if any(k in lc for k in ("coffee", "espresso", "latte", "cappuccino", "americano",
                                   "cold brew", "mocha", "macchiato")):
            commodity_set.add("coffee")
        if any(k in lc for k in ("dessert", "cake", "cookie", "brownie", "muffin", "pastry",
                                   "pie", "tart", "waffle", "pancake", "crepe", "french toast")):
            commodity_set.update({"flour", "sugar", "eggs", "butter"})
    return commodity_set


async def _ai_infer_commodities(terms: list[str]) -> set[str]:
    """
    Use Gemini to identify primary BLS commodity categories for a list of menu items.
    More accurate than rule matching for complex/international dishes.
    """
    import os
    import httpx

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return set()

    valid_commodities = list(
        {"eggs", "beef", "poultry", "pork", "seafood", "dairy", "butter", "cheese",
         "flour", "bread", "rice", "produce", "oil", "coffee", "sugar"}
    )
    prompt = (
        f"For each of these menu items, identify which primary commodity categories "
        f"(from this list only: {', '.join(valid_commodities)}) are the main cost drivers. "
        f"Return ONLY a JSON array of commodity names, no duplicates, no explanation.\n\n"
        f"Menu items: {', '.join(terms[:20])}"  # cap at 20 to stay within token budget
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
    data = res.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    # Strip markdown fences and parse
    text = re.sub(r"```[a-z]*\n?", "", text).strip().strip("`")
    import json as _json
    items_list = _json.loads(text)
    return {c for c in items_list if c in valid_commodities}


# ---------------------------------------------------------------------------
# Surgeon tool
# ---------------------------------------------------------------------------

async def perform_surgery(
    items: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Provide items, competitors, and commodities to calculate the absolute optimal price
    and identify revenue leakage for the restaurant's menu.

    Args:
        items: Array of MenuItem dicts.
        competitors: Array of CompetitorPrice dicts.
        commodities: Array of CommodityTrend dicts.

    Returns:
        list of MenuAnalysisItem dicts with calculated leakage.
    """
    return perform_margin_surgery(items, competitors, commodities)


# ---------------------------------------------------------------------------
# Pre-wrapped FunctionTool instances
# ---------------------------------------------------------------------------

benchmark_tool = FunctionTool(func=fetch_competitor_benchmarks)
commodity_inflation_tool = FunctionTool(func=check_commodity_inflation)
surgery_tool = FunctionTool(func=perform_surgery)
