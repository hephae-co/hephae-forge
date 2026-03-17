"""SchoolDigger API client for education data as economic proxy."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SCHOOLDIGGER_URL = "https://api.schooldigger.com/v2.0/schools"


def _classify_economic_stress(free_reduced_pct: float) -> str:
    """Classify economic stress based on free/reduced lunch percentage."""
    if free_reduced_pct < 30.0:
        return "low"
    elif free_reduced_pct <= 50.0:
        return "moderate"
    return "high"


def _classify_family_friendliness(school_count: int, avg_rating: float) -> str:
    """Rate family friendliness based on school count and ratings."""
    if school_count >= 5 and avg_rating >= 3.5:
        return "high"
    elif school_count >= 2 and avg_rating >= 2.5:
        return "moderate"
    return "low"


async def query_school_data(
    zip_code: str,
    app_id: str = "",
    app_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query SchoolDigger API for education data by zip code.

    Args:
        zip_code: US zip code to search schools in.
        app_id: SchoolDigger application ID. Falls back to SCHOOLDIGGER_APP_ID env var.
        app_key: SchoolDigger application key. Falls back to SCHOOLDIGGER_APP_KEY env var.
        cache_reader: Optional async fn(source, key, sub) -> dict | None
        cache_writer: Optional async fn(source, key, sub, data) -> None

    Returns:
        Dict with schoolCount, avgRating, freeReducedLunchPct, economicStressLevel,
        topSchools, and familyFriendliness.
    """
    empty: dict[str, Any] = {}

    app_id = app_id or os.getenv("SCHOOLDIGGER_APP_ID", "")
    app_key = app_key or os.getenv("SCHOOLDIGGER_APP_KEY", "")

    if not app_id or not app_key:
        logger.warning("[SchoolDigger] No SCHOOLDIGGER_APP_ID/SCHOOLDIGGER_APP_KEY configured")
        return empty

    if cache_reader:
        try:
            cached = await cache_reader("schooldigger", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        # SchoolDigger requires a state abbreviation; derive from zip code prefix
        # We pass zip and let the API filter, but we need the state param.
        # Fetch state from Zippopotam as a lightweight lookup.
        state = await _resolve_state(zip_code)
        if not state:
            logger.warning(f"[SchoolDigger] Could not resolve state for zip {zip_code}")
            return empty

        params: dict[str, str] = {
            "st": state,
            "zip": zip_code,
            "appID": app_id,
            "appKey": app_key,
            "perPage": "10",
        }

        logger.info(f"[SchoolDigger] Querying schools in {zip_code} ({state})")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_SCHOOLDIGGER_URL, params=params)

        if resp.status_code != 200:
            logger.warning(f"[SchoolDigger] API returned {resp.status_code}")
            return empty

        data = resp.json()
        schools = data.get("schoolList", [])

        if not schools:
            logger.info(f"[SchoolDigger] No schools found for zip {zip_code}")
            return empty

        school_count = data.get("numberOfSchools", len(schools))

        # Compute averages
        ratings: list[float] = []
        lunch_pcts: list[float] = []
        top_schools: list[dict[str, Any]] = []

        for s in schools:
            # Rating
            ranking = s.get("rankHistory", [])
            if ranking:
                latest_rank = ranking[0]
                rank_score = latest_rank.get("rankOf", 0)
                if rank_score and rank_score > 0:
                    # SchoolDigger uses a 0-5 star scale
                    stars = latest_rank.get("rankStars", 0)
                    if stars:
                        ratings.append(float(stars))

            # Free/reduced lunch
            school_yr_data = s.get("schoolYearlyDetails", [])
            if school_yr_data:
                latest_yr = school_yr_data[0]
                pct = latest_yr.get("percentofStudentsFreeDiscLunch")
                if pct is not None:
                    lunch_pcts.append(float(pct))

            # Build top school entry
            school_entry: dict[str, Any] = {
                "name": s.get("schoolName", ""),
                "rating": 0.0,
                "type": s.get("schoolLevel", ""),
                "freeReducedLunchPct": 0.0,
            }
            if ranking:
                school_entry["rating"] = float(ranking[0].get("rankStars", 0))
            if school_yr_data:
                pct_val = school_yr_data[0].get("percentofStudentsFreeDiscLunch")
                if pct_val is not None:
                    school_entry["freeReducedLunchPct"] = float(pct_val)
            top_schools.append(school_entry)

        # Sort top schools by rating descending, take top 3
        top_schools.sort(key=lambda s: s.get("rating", 0), reverse=True)
        top_schools = top_schools[:3]

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        avg_lunch_pct = round(sum(lunch_pcts) / len(lunch_pcts), 1) if lunch_pcts else 0.0

        stress_level = _classify_economic_stress(avg_lunch_pct)
        family_score = _classify_family_friendliness(school_count, avg_rating)

        logger.info(
            f"[SchoolDigger] Found {school_count} schools, "
            f"avgRating={avg_rating}, lunchPct={avg_lunch_pct}%, "
            f"stress={stress_level}, family={family_score}"
        )

        result: dict[str, Any] = {
            "schoolCount": school_count,
            "avgRating": avg_rating,
            "freeReducedLunchPct": avg_lunch_pct,
            "economicStressLevel": stress_level,
            "topSchools": top_schools,
            "familyFriendliness": family_score,
        }

        if cache_writer:
            try:
                await cache_writer("schooldigger", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[SchoolDigger] School data query failed: {e}")
        return empty


async def _resolve_state(zip_code: str) -> str:
    """Resolve US state abbreviation from a zip code via Zippopotam.us."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.zippopotam.us/us/{zip_code}")
            if resp.status_code != 200:
                return ""
            data = resp.json()
            places = data.get("places", [])
            if not places:
                return ""
            return places[0].get("state abbreviation", "")
    except Exception:
        return ""
