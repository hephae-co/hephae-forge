"""Yelp Fusion API client for business and competitive data."""

from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any

import httpx

logger = logging.getLogger(__name__)

YELP_BASE_URL = "https://api.yelp.com/v3"


def _build_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def _extract_address(location: dict[str, Any]) -> str:
    parts = [
        location.get("address1", ""),
        location.get("city", ""),
        location.get("state", ""),
        location.get("zip_code", ""),
    ]
    return ", ".join(p for p in parts if p)


def _compute_price_distribution(businesses: list[dict[str, Any]]) -> dict[str, int]:
    dist = {"$": 0, "$$": 0, "$$$": 0, "$$$$": 0}
    for biz in businesses:
        price = biz.get("price", "")
        if price in dist:
            dist[price] += 1
    return dist


def _extract_top_rated(businesses: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    sorted_biz = sorted(businesses, key=lambda b: (b.get("rating", 0), b.get("review_count", 0)), reverse=True)
    top = []
    for biz in sorted_biz[:limit]:
        top.append({
            "name": biz.get("name", ""),
            "rating": biz.get("rating", 0),
            "reviewCount": biz.get("review_count", 0),
            "price": biz.get("price", ""),
            "address": _extract_address(biz.get("location", {})),
        })
    return top


def _extract_recently_opened(businesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify likely new businesses — those flagged is_new or with very few reviews."""
    recent = []
    for biz in businesses:
        is_new = biz.get("is_new", False)
        review_count = biz.get("review_count", 0)
        if is_new or review_count <= 5:
            recent.append({
                "name": biz.get("name", ""),
                "rating": biz.get("rating", 0),
                "reviewCount": review_count,
                "price": biz.get("price", ""),
                "address": _extract_address(biz.get("location", {})),
            })
    return recent


def _extract_categories(businesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the most common business categories with counts."""
    counter: Counter[str] = Counter()
    for biz in businesses:
        for cat in biz.get("categories", []):
            title = cat.get("title", "")
            if title:
                counter[title] += 1
    return [{"category": name, "count": count} for name, count in counter.most_common(15)]


def _compute_saturation_level(total: int) -> str:
    if total >= 100:
        return "high"
    if total >= 40:
        return "moderate"
    if total >= 10:
        return "low"
    return "minimal"


async def query_yelp_businesses(
    zip_code: str,
    business_type: str = "",
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query Yelp Fusion API for business data in a given zip code.

    Args:
        zip_code: ZIP code to search.
        business_type: Optional business type / search term.
        api_key: Yelp API key. Falls back to YELP_API_KEY env var.
        cache_reader: Optional async fn(source, industry, state) -> dict | None
        cache_writer: Optional async fn(source, industry, state, data) -> None

    Returns:
        Dict with totalBusinesses, avgRating, priceDistribution, topRated,
        recentlyOpened, categories, zipCode, and businessType.
    """
    empty: dict[str, Any] = {
        "zipCode": zip_code,
        "businessType": business_type,
        "totalBusinesses": 0,
        "avgRating": 0.0,
        "priceDistribution": {"$": 0, "$$": 0, "$$$": 0, "$$$$": 0},
        "topRated": [],
        "recentlyOpened": [],
        "categories": [],
    }

    api_key = api_key or os.getenv("YELP_API_KEY", "")
    if not api_key:
        logger.warning("[Yelp] No API key provided (set YELP_API_KEY env var)")
        return empty

    if cache_reader:
        try:
            cached = await cache_reader("yelp", business_type or "general", zip_code)
            if cached:
                return cached
        except Exception:
            pass

    try:
        params: dict[str, Any] = {
            "location": zip_code,
            "limit": 50,
            "sort_by": "best_match",
        }
        if business_type:
            params["term"] = business_type

        url = f"{YELP_BASE_URL}/businesses/search"
        headers = _build_headers(api_key)

        logger.info(f"[Yelp] Querying businesses in {zip_code} (term={business_type or 'all'})")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logger.warning(f"[Yelp] API returned {response.status_code}: {response.text[:200]}")
            return empty

        data = response.json()
        businesses = data.get("businesses", [])
        total = data.get("total", len(businesses))

        # Compute average rating
        ratings = [b.get("rating", 0) for b in businesses if b.get("rating")]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        result: dict[str, Any] = {
            "zipCode": zip_code,
            "businessType": business_type,
            "totalBusinesses": total,
            "avgRating": avg_rating,
            "priceDistribution": _compute_price_distribution(businesses),
            "topRated": _extract_top_rated(businesses),
            "recentlyOpened": _extract_recently_opened(businesses),
            "categories": _extract_categories(businesses),
        }

        logger.info(f"[Yelp] Found {total} businesses, avg rating {avg_rating}")

        if cache_writer:
            try:
                await cache_writer("yelp", business_type or "general", zip_code, result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[Yelp] Business query failed for zip={zip_code}: {e}")
        return empty


async def query_yelp_competition(
    zip_code: str,
    business_type: str,
    api_key: str = "",
) -> dict[str, Any]:
    """Query Yelp for competitive density data in a zip code.

    Focuses on total count, saturation level, and new entrants for
    a specific business type.

    Args:
        zip_code: ZIP code to search.
        business_type: Business type / search term (required).
        api_key: Yelp API key. Falls back to YELP_API_KEY env var.

    Returns:
        Dict with totalCompetitors, saturationLevel, newEntrants,
        avgCompetitorRating, priceDistribution, zipCode, and businessType.
    """
    empty: dict[str, Any] = {
        "zipCode": zip_code,
        "businessType": business_type,
        "totalCompetitors": 0,
        "saturationLevel": "unknown",
        "newEntrants": [],
        "avgCompetitorRating": 0.0,
        "priceDistribution": {"$": 0, "$$": 0, "$$$": 0, "$$$$": 0},
    }

    api_key = api_key or os.getenv("YELP_API_KEY", "")
    if not api_key:
        logger.warning("[Yelp] No API key provided (set YELP_API_KEY env var)")
        return empty

    try:
        params: dict[str, Any] = {
            "location": zip_code,
            "term": business_type,
            "limit": 50,
            "sort_by": "best_match",
        }

        url = f"{YELP_BASE_URL}/businesses/search"
        headers = _build_headers(api_key)

        logger.info(f"[Yelp] Querying competition for '{business_type}' in {zip_code}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logger.warning(f"[Yelp] API returned {response.status_code}: {response.text[:200]}")
            return empty

        data = response.json()
        businesses = data.get("businesses", [])
        total = data.get("total", len(businesses))

        ratings = [b.get("rating", 0) for b in businesses if b.get("rating")]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        new_entrants = _extract_recently_opened(businesses)

        result: dict[str, Any] = {
            "zipCode": zip_code,
            "businessType": business_type,
            "totalCompetitors": total,
            "saturationLevel": _compute_saturation_level(total),
            "newEntrants": new_entrants,
            "avgCompetitorRating": avg_rating,
            "priceDistribution": _compute_price_distribution(businesses),
        }

        logger.info(
            f"[Yelp] Competition: {total} competitors, "
            f"saturation={result['saturationLevel']}, "
            f"{len(new_entrants)} new entrants"
        )

        return result

    except Exception as e:
        logger.error(f"[Yelp] Competition query failed for zip={zip_code}: {e}")
        return empty
