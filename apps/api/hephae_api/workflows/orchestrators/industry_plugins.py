"""Industry plugin registry — business type classification.

Fetcher functions have been migrated to pulse_fetch_tools.py with
cache-through logic. This module retains only type classification sets
and the is_food_business() helper used across the codebase.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Business type classification
# ---------------------------------------------------------------------------

FOOD_TYPES = {
    "restaurants", "restaurant", "bakeries", "bakery", "cafes", "cafe",
    "coffee shops", "coffee", "pizza", "pizzeria", "tacos", "taqueria",
    "delis", "deli", "ice cream", "gelato", "juice bar", "smoothie",
    "seafood", "fish market", "butcher", "grocery", "supermarket",
}

RETAIL_TYPES = {
    "retail", "clothing", "boutique", "gift shop", "hardware",
    "electronics", "bookstore", "pet store", "florist",
}

BEAUTY_TYPES = {
    "salons", "salon", "spas", "spa", "barbers", "barber",
    "nail salon", "beauty", "wellness",
}

SERVICE_TYPES = {
    "auto repair", "laundry", "dry cleaning", "fitness", "gym",
    "tutoring", "daycare", "veterinary", "vet",
}


def _matches(business_type: str, type_set: set[str]) -> bool:
    normalized = business_type.lower().strip()
    return normalized in type_set or any(t in normalized for t in type_set)


def is_food_business(business_type: str) -> bool:
    return _matches(business_type, FOOD_TYPES)


def classify_business_type(business_type: str) -> str:
    """Return the broad category for a business type."""
    if _matches(business_type, FOOD_TYPES):
        return "food"
    if _matches(business_type, RETAIL_TYPES):
        return "retail"
    if _matches(business_type, BEAUTY_TYPES):
        return "beauty"
    if _matches(business_type, SERVICE_TYPES):
        return "service"
    return "general"
