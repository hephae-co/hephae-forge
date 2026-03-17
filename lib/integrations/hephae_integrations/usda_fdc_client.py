"""USDA FoodData Central API client — branded food product data.

Supplements NASS QuickStats (commodity prices) with retail-level food data:
ingredient composition, branded product info, and food category trends.

API docs: https://fdc.nal.usda.gov/api-guide
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FDC_API_URL = "https://api.nal.usda.gov/fdc/v1"


async def query_fdc_food_prices(
    business_type: str,
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query FoodData Central for branded food product data relevant to a business type.

    Returns price-relevant data: common ingredients, branded products,
    and food category information useful for menu planning.
    """
    empty: dict[str, Any] = {"ingredients": [], "highlights": []}

    api_key = api_key or os.getenv("USDA_FDC_API_KEY", "")
    if not api_key:
        logger.warning("[USDA-FDC] No USDA_FDC_API_KEY configured")
        return empty

    if cache_reader:
        try:
            cached = await cache_reader("usda_fdc", business_type, "")
            if cached:
                return cached
        except Exception:
            pass

    # Map business types to key ingredients to search
    BUSINESS_INGREDIENTS: dict[str, list[str]] = {
        "restaurants": ["chicken breast", "ground beef", "rice", "olive oil", "butter", "flour"],
        "bakeries": ["all-purpose flour", "butter", "sugar", "eggs", "vanilla extract", "cream cheese"],
        "pizza": ["mozzarella cheese", "pizza sauce", "pepperoni", "flour", "olive oil"],
        "cafes": ["coffee beans", "milk", "oat milk", "butter", "flour", "sugar"],
        "coffee": ["coffee beans", "whole milk", "oat milk", "almond milk", "vanilla syrup"],
        "tacos": ["ground beef", "chicken thigh", "tortillas", "avocado", "sour cream", "cheese"],
        "ice cream": ["heavy cream", "whole milk", "sugar", "vanilla extract", "eggs"],
    }

    normalized = business_type.lower().strip().rstrip("s")
    ingredients = BUSINESS_INGREDIENTS.get(normalized, BUSINESS_INGREDIENTS.get("restaurants", []))

    try:
        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20) as client:
            for ingredient in ingredients[:6]:
                url = f"{FDC_API_URL}/foods/search"
                params = {
                    "api_key": api_key,
                    "query": ingredient,
                    "dataType": "Branded,Survey (FNDDS)",
                    "pageSize": 3,
                    "sortBy": "dataType.keyword",
                    "sortOrder": "asc",
                }
                response = await client.get(url, params=params)
                if response.status_code != 200:
                    continue

                data = response.json()
                foods = data.get("foods", [])
                if not foods:
                    continue

                # Extract the most relevant result
                food = foods[0]
                nutrients = {n["nutrientName"]: n.get("value", 0) for n in food.get("foodNutrients", [])[:10]}

                results.append({
                    "ingredient": ingredient,
                    "description": food.get("description", ""),
                    "brandOwner": food.get("brandOwner", ""),
                    "servingSize": food.get("servingSize"),
                    "servingUnit": food.get("servingSizeUnit", ""),
                    "calories": nutrients.get("Energy", 0),
                    "protein": nutrients.get("Protein", 0),
                    "fat": nutrients.get("Total lipid (fat)", 0),
                    "dataType": food.get("dataType", ""),
                })

        # Generate highlights
        highlights: list[str] = []
        for r in results:
            if r.get("brandOwner"):
                highlights.append(f"{r['ingredient']}: common brand = {r['brandOwner']}")

        logger.info(f"[USDA-FDC] Got {len(results)} ingredient profiles for {business_type}")

        result = {
            "ingredients": results,
            "highlights": highlights,
            "businessType": business_type,
        }

        if cache_writer:
            try:
                await cache_writer("usda_fdc", business_type, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[USDA-FDC] Query failed: {e}")
        return empty
