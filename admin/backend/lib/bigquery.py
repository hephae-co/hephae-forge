"""BigQuery integration for Google Trends public dataset."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.cloud import bigquery

from backend.types import TrendsData, TrendsTerm, RisingTerm

logger = logging.getLogger(__name__)

_client: bigquery.Client | None = None

INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "bakeries": ["bakery", "bread", "cake", "pastry", "donut", "cupcake", "sourdough", "croissant", "gluten free"],
    "restaurants": ["restaurant", "dining", "food delivery", "takeout", "brunch", "catering", "fast food"],
    "laundromats": ["laundry", "laundromat", "dry cleaning", "wash and fold", "coin laundry"],
    "hairdressers": ["hair salon", "barber", "haircut", "hairdresser", "hair color", "braids"],
    "gyms": ["gym", "fitness", "workout", "personal trainer", "crossfit", "yoga", "pilates"],
    "coffee": ["coffee", "coffee shop", "espresso", "latte", "cafe", "cold brew"],
    "pizza": ["pizza", "pizzeria", "pizza delivery", "pizza near me"],
    "tacos": ["taco", "taqueria", "mexican food", "burrito"],
    "ice_cream": ["ice cream", "gelato", "frozen yogurt", "ice cream shop"],
    "nail_salons": ["nail salon", "manicure", "pedicure", "nails near me"],
    "auto_repair": ["auto repair", "mechanic", "oil change", "car repair", "brake repair"],
    "pet_stores": ["pet store", "pet grooming", "dog food", "pet supplies"],
    "florists": ["florist", "flowers", "flower delivery", "bouquet"],
    "pharmacies": ["pharmacy", "drugstore", "prescription", "medicine"],
}

# Cache resolved DMA names
_dma_cache: dict[str, str | None] = {}


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client()
    return _client


async def _run_query(query: str, params: dict[str, str]) -> list[dict[str, Any]]:
    """Execute a BigQuery parameterized query in a thread."""
    client = _get_client()
    job_params = [
        bigquery.ScalarQueryParameter(k, "STRING", v) for k, v in params.items()
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=job_params)

    def _execute():
        job = client.query(query, job_config=job_config)
        return [dict(row) for row in job.result()]

    return await asyncio.to_thread(_execute)


async def _resolve_dma_name(dma_name: str) -> str | None:
    """Resolve a fuzzy DMA name to the exact BigQuery dma_name value."""
    cache_key = dma_name.lower().strip()
    if cache_key in _dma_cache:
        return _dma_cache[cache_key]

    import re
    core_name = re.sub(r"[*#_`]", "", dma_name)
    core_name = re.sub(r"\s*(DMA|Metropolitan Area|Metro Area|Region|Area)\s*", " ", core_name, flags=re.IGNORECASE)
    core_name = re.sub(r"[-/].*$", "", core_name).strip()

    pattern = f"%{core_name}%"
    query = """
        SELECT DISTINCT dma_name
        FROM `bigquery-public-data.google_trends.top_terms`
        WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
          AND dma_name LIKE @pattern
        LIMIT 5
    """
    rows = await _run_query(query, {"pattern": pattern})

    resolved = None
    if len(rows) == 1:
        resolved = rows[0]["dma_name"]
    elif len(rows) > 1:
        exact = next((r for r in rows if r["dma_name"].lower().startswith(core_name.lower())), None)
        resolved = exact["dma_name"] if exact else rows[0]["dma_name"]

    _dma_cache[cache_key] = resolved
    return resolved


async def query_google_trends(dma_name: str) -> TrendsData:
    """Query Google Trends BigQuery public dataset for a DMA region."""
    empty = TrendsData()
    if not dma_name:
        return empty

    try:
        resolved = await _resolve_dma_name(dma_name)
        if not resolved:
            logger.warning(f'[BigQuery] Could not resolve DMA name "{dma_name}"')
            return empty

        logger.info(f'[BigQuery] Resolved DMA "{dma_name}" → "{resolved}"')

        top_query = """
            SELECT term, rank, score, week
            FROM `bigquery-public-data.google_trends.top_terms`
            WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
              AND dma_name = @dmaName
            ORDER BY score DESC
            LIMIT 25
        """
        rising_query = """
            SELECT term, percent_gain, rank, score, week
            FROM `bigquery-public-data.google_trends.top_rising_terms`
            WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
              AND dma_name = @dmaName
            ORDER BY percent_gain DESC
            LIMIT 25
        """

        top_rows, rising_rows = await asyncio.gather(
            _run_query(top_query, {"dmaName": resolved}),
            _run_query(rising_query, {"dmaName": resolved}),
        )

        return TrendsData(
            topTerms=[
                TrendsTerm(term=r["term"], rank=r["rank"], score=r["score"], week=str(r.get("week", "")))
                for r in top_rows
            ],
            risingTerms=[
                RisingTerm(
                    term=r["term"], percent_gain=r["percent_gain"],
                    rank=r["rank"], score=r["score"], week=str(r.get("week", ""))
                )
                for r in rising_rows
            ],
        )
    except Exception as e:
        logger.error(f'[BigQuery] Google Trends query failed for DMA "{dma_name}": {e}')
        return empty


async def query_industry_trends(
    dma_name: str, industry: str
) -> dict[str, list[dict[str, Any]]]:
    """Query industry-relevant Google Trends, filtered by keyword map."""
    empty: dict[str, list] = {"topTerms": [], "risingTerms": []}
    if not dma_name:
        return empty

    try:
        resolved = await _resolve_dma_name(dma_name)
        if not resolved:
            return empty

        normalized = industry.lower().replace(" ", "_")
        keywords = (
            INDUSTRY_KEYWORDS.get(normalized)
            or INDUSTRY_KEYWORDS.get(normalized.rstrip("s"))
            or [industry.lower()]
        )

        like_conditions = " OR ".join(f"LOWER(term) LIKE @kw{i}" for i in range(len(keywords)))
        params = {"dmaName": resolved}
        for i, kw in enumerate(keywords):
            params[f"kw{i}"] = f"%{kw.lower()}%"

        top_query = f"""
            SELECT term, score
            FROM `bigquery-public-data.google_trends.top_terms`
            WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
              AND dma_name = @dmaName
              AND ({like_conditions})
            ORDER BY score DESC
            LIMIT 15
        """
        rising_query = f"""
            SELECT term, percent_gain
            FROM `bigquery-public-data.google_trends.top_rising_terms`
            WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
              AND dma_name = @dmaName
              AND ({like_conditions})
            ORDER BY percent_gain DESC
            LIMIT 15
        """

        top_rows, rising_rows = await asyncio.gather(
            _run_query(top_query, params),
            _run_query(rising_query, params),
        )

        return {
            "topTerms": [{"term": r["term"], "score": r["score"]} for r in top_rows],
            "risingTerms": [{"term": r["term"], "percent_gain": r["percent_gain"]} for r in rising_rows],
        }
    except Exception as e:
        logger.error(f"[BigQuery] Industry trends query failed: {e}")
        return empty
