"""CDC PLACES health metrics client by ZCTA (ZIP Code Tabulation Area)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CDC_PLACES_URL = "https://data.cdc.gov/resource/qnzd-25i4.json"

_MEASURE_ID_TO_KEY: dict[str, str] = {
    "OBESITY": "obesity",
    "DIABETES": "diabetes",
    "DEPRESSION": "depression",
    "BINGE": "bingeDrinking",
    "SMOKING": "smoking",
    "LPA": "noExercise",
    "SLEEP": "shortSleep",
    "ACCESS2": "noInsurance",
    "FOODINSECU": "foodInsecurity",
    "HOUSINSECU": "housingInsecurity",
}

_MEASURE_IDS = ",".join(f"'{m}'" for m in _MEASURE_ID_TO_KEY)


def _classify_health_profile(metrics: dict[str, float]) -> str:
    """Classify health profile based on average of obesity + diabetes + depression."""
    obesity = metrics.get("obesity", 0.0)
    diabetes = metrics.get("diabetes", 0.0)
    avg = (obesity + diabetes) / 2
    if avg < 20:
        return "healthy"
    if avg > 30:
        return "at_risk"
    return "moderate"


def _generate_demand_signals(metrics: dict[str, float]) -> list[str]:
    """Generate 2-3 consumer demand signals from health metrics."""
    signals: list[str] = []

    if metrics.get("depression", 0) > 20:
        signals.append("High depression prevalence -> wellness and mental health services demand")
    if metrics.get("noExercise", 0) > 30:
        signals.append("Low physical activity -> gym/fitness studio opportunity")
    if metrics.get("foodInsecurity", 0) > 15:
        signals.append("High food insecurity -> discount/value positioning resonates")
    if metrics.get("obesity", 0) > 35:
        signals.append("High obesity rate -> healthy dining and nutrition services demand")
    if metrics.get("noInsurance", 0) > 15:
        signals.append("High uninsured rate -> affordable healthcare and preventive services demand")
    if metrics.get("shortSleep", 0) > 35:
        signals.append("High short sleep prevalence -> wellness/recovery services opportunity")
    if metrics.get("bingeDrinking", 0) > 20:
        signals.append("Elevated binge drinking -> nightlife market but also recovery services demand")
    if metrics.get("housingInsecurity", 0) > 20:
        signals.append("High housing insecurity -> cost-conscious consumer base, value-oriented businesses")
    if metrics.get("smoking", 0) > 20:
        signals.append("High smoking rate -> health-conscious alternatives and cessation services demand")
    if metrics.get("diabetes", 0) > 15:
        signals.append("Elevated diabetes prevalence -> sugar-free/healthy menu options opportunity")

    # Return 2-3 most relevant signals
    return signals[:3]


async def query_health_metrics(
    zip_code: str,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query CDC PLACES API for health metrics by ZIP code (ZCTA).

    Args:
        zip_code: 5-digit ZIP code string.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with zipCode, metrics, population18Plus, healthProfile, and
        consumerDemandSignals. Returns empty dict on failure.
    """
    empty: dict[str, Any] = {}

    if not zip_code or len(zip_code.strip()) != 5:
        logger.warning("[CDC_PLACES] Invalid zip code provided")
        return empty

    zip_code = zip_code.strip()

    if cache_reader:
        try:
            cached = await cache_reader("cdc_places", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        where_clause = (
            f"locationid='{zip_code}' AND "
            f"measureid in ({_MEASURE_IDS})"
        )
        params = {
            "$where": where_clause,
            "$limit": 50,
        }

        logger.info(f"[CDC_PLACES] Querying health metrics for zip={zip_code}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(CDC_PLACES_URL, params=params)

        if response.status_code != 200:
            logger.warning(f"[CDC_PLACES] API returned {response.status_code}")
            return empty

        records = response.json()
        if not records:
            logger.warning(f"[CDC_PLACES] No data found for zip={zip_code}")
            return empty

        metrics: dict[str, float] = {}
        population_18_plus = 0

        for record in records:
            measure_id = record.get("measureid", "")
            key = _MEASURE_ID_TO_KEY.get(measure_id)
            if not key:
                continue

            try:
                value = float(record.get("data_value", 0))
            except (ValueError, TypeError):
                continue

            metrics[key] = round(value, 1)

            if not population_18_plus:
                try:
                    population_18_plus = int(float(record.get("totalpopulation", 0)))
                except (ValueError, TypeError):
                    pass

        if not metrics:
            logger.warning(f"[CDC_PLACES] No parseable metrics for zip={zip_code}")
            return empty

        health_profile = _classify_health_profile(metrics)
        demand_signals = _generate_demand_signals(metrics)

        logger.info(
            f"[CDC_PLACES] zip={zip_code}: {len(metrics)} metrics, "
            f"profile={health_profile}, pop18+={population_18_plus}"
        )

        result: dict[str, Any] = {
            "zipCode": zip_code,
            "metrics": metrics,
            "population18Plus": population_18_plus,
            "healthProfile": health_profile,
            "consumerDemandSignals": demand_signals,
        }

        if cache_writer:
            try:
                await cache_writer("cdc_places", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[CDC_PLACES] Query failed for zip={zip_code}: {e}")
        return empty
