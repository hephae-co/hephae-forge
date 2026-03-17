"""BigQuery public dataset queries for Weekly Pulse signals.

Replaces external API clients with free, reliable BigQuery public datasets:
- utility_us.zipcode_area → geography bridging (zip → lat/lon/county/state)
- census_bureau_acs.zip_codes_2018_5yr → demographics, income, poverty, housing
- geo_openstreetmap.planet_features_points → business density, competition count
- noaa_gsod → historical weather patterns for seasonal baselines
- bls.cpi_u → CPI data (stale to 2021, keep API as primary for recent data)

All queries use parameterized SQL to prevent injection. Results are cached
in-memory for the duration of a pulse generation run.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

_client: bigquery.Client | None = None
_geo_cache: dict[str, Any] = {}


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client()
    return _client


async def _run_query(
    query: str,
    params: list[bigquery.ScalarQueryParameter] | None = None,
    array_params: list[bigquery.ArrayQueryParameter] | None = None,
) -> list[dict[str, Any]]:
    """Execute a BigQuery parameterized query in a thread."""
    client = _get_client()
    all_params: list = list(params or []) + list(array_params or [])
    job_config = bigquery.QueryJobConfig(query_parameters=all_params) if all_params else bigquery.QueryJobConfig()

    def _execute():
        job = client.query(query, job_config=job_config)
        return [dict(row) for row in job.result()]

    return await asyncio.to_thread(_execute)


# ── Geography Bridging ───────────────────────────────────────────────────


@dataclass
class ZipGeography:
    zip_code: str
    latitude: float
    longitude: float
    city: str
    state_code: str
    state_name: str
    state_fips: str
    county: str


async def resolve_zip_geography(zip_code: str) -> ZipGeography | None:
    """Resolve a zip code to its geographic context via BQ utility_us.

    Returns ZipGeography with lat/lon, city, state, county. Cached in-memory.
    """
    if zip_code in _geo_cache:
        return _geo_cache[zip_code]

    try:
        rows = await _run_query(
            """
            SELECT zipcode, latitude, longitude, city, state_code, state_name,
                   state_fips, county
            FROM `bigquery-public-data.utility_us.zipcode_area`
            WHERE zipcode = @zipCode
            LIMIT 1
            """,
            params=[bigquery.ScalarQueryParameter("zipCode", "STRING", zip_code)],
        )

        if not rows:
            logger.warning(f"[BQ:GEO] No geography found for zip {zip_code}")
            _geo_cache[zip_code] = None
            return None

        row = rows[0]
        geo = ZipGeography(
            zip_code=zip_code,
            latitude=row.get("latitude", 0.0),
            longitude=row.get("longitude", 0.0),
            city=row.get("city", ""),
            state_code=row.get("state_code", ""),
            state_name=row.get("state_name", ""),
            state_fips=row.get("state_fips", ""),
            county=row.get("county", ""),
        )
        _geo_cache[zip_code] = geo
        logger.info(f"[BQ:GEO] Resolved {zip_code} → {geo.city}, {geo.state_code} ({geo.county} County)")
        return geo

    except Exception as e:
        logger.error(f"[BQ:GEO] Geography resolution failed for {zip_code}: {e}")
        return None


# ── Census ACS Demographics ──────────────────────────────────────────────

async def query_census_demographics(zip_code: str) -> dict[str, Any]:
    """Query Census Bureau ACS 5-year data for a ZCTA (zip code).

    Returns demographics, income, poverty, housing, education proxies.
    Replaces: SchoolDigger API, partial FBI crime proxy (poverty as safety proxy).
    """
    empty: dict[str, Any] = {}

    try:
        rows = await _run_query(
            """
            SELECT
                geo_id,
                total_pop,
                median_age,
                median_income,
                income_per_capita,
                poverty,
                pop_determined_poverty_status,
                housing_units,
                occupied_housing_units,
                vacant_housing_units,
                median_rent,
                percent_income_spent_on_rent,
                owner_occupied_housing_units_median_value,
                children,
                children_in_single_female_hh
            FROM `bigquery-public-data.census_bureau_acs.zip_codes_2018_5yr`
            WHERE geo_id = @zcta
            LIMIT 1
            """,
            params=[bigquery.ScalarQueryParameter("zcta", "STRING", zip_code)],
        )

        if not rows:
            logger.info(f"[BQ:CENSUS] No ACS data for ZCTA {zip_code}")
            return empty

        row = rows[0]
        total_pop = row.get("total_pop") or 0
        poverty = row.get("poverty") or 0
        poverty_status_pop = row.get("pop_determined_poverty_status") or 0
        poverty_rate = round((poverty / poverty_status_pop) * 100, 1) if poverty_status_pop > 0 else 0
        median_income = row.get("median_income") or 0

        # Economic stress level based on poverty rate + income
        if poverty_rate > 20 or median_income < 35000:
            economic_stress = "high"
        elif poverty_rate > 12 or median_income < 55000:
            economic_stress = "moderate"
        else:
            economic_stress = "low"

        # Price sensitivity signal
        if median_income < 40000:
            price_sensitivity = "high"
        elif median_income < 65000:
            price_sensitivity = "moderate"
        else:
            price_sensitivity = "low"

        result = {
            "source": "census_acs_2018_5yr",
            "zipCode": zip_code,
            "totalPopulation": int(total_pop),
            "medianAge": round(row.get("median_age") or 0, 1),
            "medianHouseholdIncome": int(median_income),
            "incomePerCapita": int(row.get("income_per_capita") or 0),
            "povertyRate": poverty_rate,
            "economicStressLevel": economic_stress,
            "priceSensitivity": price_sensitivity,
            "housingUnits": int(row.get("housing_units") or 0),
            "occupancyRate": round((row.get("occupied_housing_units") or 0) / max(row.get("housing_units") or 1, 1) * 100, 1),
            "vacancyRate": round((row.get("vacant_housing_units") or 0) / max(row.get("housing_units") or 1, 1) * 100, 1),
            "medianRent": int(row.get("median_rent") or 0),
            "rentBurden": round(row.get("percent_income_spent_on_rent") or 0, 1),
            "medianHomeValue": int(row.get("owner_occupied_housing_units_median_value") or 0),
            "childrenPop": int(row.get("children") or 0),
        }

        logger.info(f"[BQ:CENSUS] Got demographics for {zip_code}: pop={int(total_pop)}, income=${int(median_income):,}")
        return result

    except Exception as e:
        logger.error(f"[BQ:CENSUS] Query failed for {zip_code}: {e}")
        return empty


# ── OSM Business Density ─────────────────────────────────────────────────

# Mapping from business types to OSM amenity/shop tags
OSM_BUSINESS_TAGS: dict[str, dict[str, list[str]]] = {
    "restaurants": {"amenity": ["restaurant", "fast_food", "food_court"], "shop": []},
    "bakeries": {"amenity": ["cafe"], "shop": ["bakery"]},
    "cafes": {"amenity": ["cafe"], "shop": ["coffee"]},
    "coffee": {"amenity": ["cafe"], "shop": ["coffee"]},
    "pizza": {"amenity": ["restaurant", "fast_food"], "shop": []},
    "retail": {"amenity": [], "shop": ["clothes", "shoes", "gift", "department_store", "variety_store"]},
    "salon": {"amenity": [], "shop": ["hairdresser", "beauty"]},
    "barber": {"amenity": [], "shop": ["hairdresser"]},
    "gym": {"amenity": [], "shop": []},  # OSM uses leisure=fitness_centre
    "grocery": {"amenity": [], "shop": ["supermarket", "convenience", "greengrocer"]},
    "default": {"amenity": ["restaurant", "cafe", "fast_food", "bar", "pub"], "shop": ["convenience", "supermarket"]},
}


async def query_osm_business_density(
    latitude: float,
    longitude: float,
    business_type: str = "",
    radius_m: int = 1500,
) -> dict[str, Any]:
    """Count businesses near a location via OSM BigQuery data.

    Uses planet_features_points for efficient spatial queries.
    Replaces: Yelp Fusion API (no API key needed).
    """
    empty: dict[str, Any] = {}

    try:
        normalized = business_type.lower().strip().rstrip("s")
        tags = OSM_BUSINESS_TAGS.get(normalized, OSM_BUSINESS_TAGS["default"])
        amenity_tags = tags["amenity"]
        shop_tags = tags["shop"]

        # Build filter conditions
        conditions = []
        params: list = [
            bigquery.ScalarQueryParameter("lat", "FLOAT64", latitude),
            bigquery.ScalarQueryParameter("lon", "FLOAT64", longitude),
            bigquery.ScalarQueryParameter("radius", "INT64", radius_m),
        ]

        if amenity_tags:
            conditions.append(
                "EXISTS(SELECT 1 FROM UNNEST(all_tags) t WHERE t.key = 'amenity' AND t.value IN UNNEST(@amenityTags))"
            )
            params.append(bigquery.ArrayQueryParameter("amenityTags", "STRING", amenity_tags))
        if shop_tags:
            conditions.append(
                "EXISTS(SELECT 1 FROM UNNEST(all_tags) t WHERE t.key = 'shop' AND t.value IN UNNEST(@shopTags))"
            )
            params.append(bigquery.ArrayQueryParameter("shopTags", "STRING", shop_tags))

        if not conditions:
            # Fallback: count all named amenities
            conditions.append(
                "EXISTS(SELECT 1 FROM UNNEST(all_tags) t WHERE t.key = 'amenity')"
            )

        filter_sql = " OR ".join(f"({c})" for c in conditions)

        query = f"""
            SELECT
                (SELECT t.value FROM UNNEST(all_tags) t WHERE t.key = 'name' LIMIT 1) AS name,
                (SELECT t.value FROM UNNEST(all_tags) t WHERE t.key = 'amenity' LIMIT 1) AS amenity,
                (SELECT t.value FROM UNNEST(all_tags) t WHERE t.key = 'shop' LIMIT 1) AS shop,
                (SELECT t.value FROM UNNEST(all_tags) t WHERE t.key = 'cuisine' LIMIT 1) AS cuisine,
                ST_DISTANCE(geometry, ST_GEOGPOINT(@lon, @lat)) AS distance_m
            FROM `bigquery-public-data.geo_openstreetmap.planet_features`
            WHERE ST_DWITHIN(geometry, ST_GEOGPOINT(@lon, @lat), @radius)
              AND EXISTS(SELECT 1 FROM UNNEST(all_tags) t WHERE t.key = 'name')
              AND ({filter_sql})
            ORDER BY distance_m
            LIMIT 200
        """

        rows = await _run_query(query, params=params[:3], array_params=[p for p in params[3:] if isinstance(p, bigquery.ArrayQueryParameter)])

        if not rows:
            logger.info(f"[BQ:OSM] No businesses found within {radius_m}m of ({latitude}, {longitude})")
            return {"totalBusinesses": 0, "saturationLevel": "minimal", "categories": {}, "nearby": []}

        # Categorize results
        categories: dict[str, int] = {}
        nearby: list[dict[str, Any]] = []
        for row in rows:
            cat = row.get("amenity") or row.get("shop") or "other"
            categories[cat] = categories.get(cat, 0) + 1
            if len(nearby) < 10:
                nearby.append({
                    "name": row.get("name", ""),
                    "category": cat,
                    "cuisine": row.get("cuisine", ""),
                    "distanceM": int(row.get("distance_m", 0)),
                })

        total = len(rows)
        if total >= 50:
            saturation = "high"
        elif total >= 20:
            saturation = "moderate"
        elif total >= 5:
            saturation = "low"
        else:
            saturation = "minimal"

        result = {
            "totalBusinesses": total,
            "saturationLevel": saturation,
            "radiusM": radius_m,
            "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
            "nearby": nearby,
        }

        logger.info(f"[BQ:OSM] Found {total} businesses ({saturation} saturation) within {radius_m}m")
        return result

    except Exception as e:
        logger.error(f"[BQ:OSM] Query failed: {e}")
        return empty


# ── NOAA Historical Weather ──────────────────────────────────────────────

async def query_noaa_weather_history(
    latitude: float,
    longitude: float,
    month: int | None = None,
) -> dict[str, Any]:
    """Query NOAA GSOD for historical weather patterns at nearest station.

    Returns 10-year averages for the given month to establish seasonal baselines.
    Supplements: NWS forecast API (which gives future, not historical).
    """
    empty: dict[str, Any] = {}
    if month is None:
        from datetime import datetime
        month = datetime.utcnow().month

    try:
        # Step 1: Find nearest US station (approximate distance via Pythagorean)
        station_rows = await _run_query(
            """
            SELECT usaf, wban, name, state, lat, lon,
                   SQRT(POW((lat - @lat) * 111, 2) + POW((lon - @lon) * 85, 2)) AS dist_km
            FROM `bigquery-public-data.noaa_gsod.stations`
            WHERE country = 'US'
              AND lat IS NOT NULL AND lon IS NOT NULL
              AND usaf != '999999'
              AND lat BETWEEN @lat - 1 AND @lat + 1
              AND lon BETWEEN @lon - 1 AND @lon + 1
            ORDER BY dist_km
            LIMIT 1
            """,
            params=[
                bigquery.ScalarQueryParameter("lat", "FLOAT64", latitude),
                bigquery.ScalarQueryParameter("lon", "FLOAT64", longitude),
            ],
        )

        if not station_rows:
            logger.info(f"[BQ:NOAA] No nearby station for ({latitude}, {longitude})")
            return empty

        station = station_rows[0]
        stn = station["usaf"]
        wban = station["wban"]
        station_name = station.get("name", "")
        dist_km = round(station.get("dist_km", 0), 1)

        # Step 2: Query 5-year historical averages for this month
        # Use recent years only
        weather_rows = await _run_query(
            f"""
            SELECT
                AVG(temp) AS avg_temp_f,
                AVG(max) AS avg_high_f,
                AVG(min) AS avg_low_f,
                AVG(CASE WHEN prcp < 99.99 THEN prcp ELSE NULL END) AS avg_precip_in,
                COUNTIF(rain_drizzle = '1') AS rain_days,
                COUNTIF(snow_ice_pellets = '1') AS snow_days,
                COUNT(*) AS observation_days
            FROM `bigquery-public-data.noaa_gsod.gsod*`
            WHERE _TABLE_SUFFIX IN ('2020', '2021', '2022', '2023', '2024')
              AND stn = @stn
              AND wban = @wban
              AND CAST(mo AS INT64) = @month
            """,
            params=[
                bigquery.ScalarQueryParameter("stn", "STRING", stn),
                bigquery.ScalarQueryParameter("wban", "STRING", wban),
                bigquery.ScalarQueryParameter("month", "INT64", month),
            ],
        )

        if not weather_rows or not weather_rows[0].get("observation_days"):
            return empty

        w = weather_rows[0]
        obs_days = w.get("observation_days", 0)
        rain_days = w.get("rain_days", 0)
        rain_pct = round((rain_days / max(obs_days, 1)) * 100, 0)

        result = {
            "station": station_name,
            "stationDistKm": dist_km,
            "month": month,
            "yearsAveraged": 5,
            "avgTempF": round(w.get("avg_temp_f") or 0, 1),
            "avgHighF": round(w.get("avg_high_f") or 0, 1),
            "avgLowF": round(w.get("avg_low_f") or 0, 1),
            "avgPrecipIn": round(w.get("avg_precip_in") or 0, 2),
            "rainDaysPct": rain_pct,
            "snowDays": w.get("snow_days", 0),
            "observationDays": obs_days,
        }

        logger.info(f"[BQ:NOAA] Historical weather for month {month}: avg {result['avgTempF']}F, {rain_pct}% rain days (station: {station_name}, {dist_km}km)")
        return result

    except Exception as e:
        logger.error(f"[BQ:NOAA] Historical weather query failed: {e}")
        return empty
