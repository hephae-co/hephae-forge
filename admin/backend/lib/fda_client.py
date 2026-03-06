"""FDA food enforcement API client."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from backend.types import FdaData, FdaEnforcement

logger = logging.getLogger(__name__)

FDA_BASE_URL = "https://api.fda.gov/food/enforcement.json"

FOOD_RELATED_INDUSTRIES = {
    "bakeries", "bakery",
    "restaurants", "restaurant",
    "coffee", "coffee shops", "cafe", "cafes",
    "pizza", "pizzeria", "pizzerias",
    "tacos", "taqueria", "taquerias",
    "ice cream", "ice_cream", "gelato",
    "catering", "caterers",
    "food trucks", "food truck",
    "delis", "deli", "delicatessen",
    "juice bars", "juice bar", "smoothie",
    "grocery", "groceries", "supermarket",
    "butcher", "butchers", "meat shop",
    "seafood", "fish market",
    "food", "dining",
}


def is_food_related_industry(industry: str) -> bool:
    return industry.lower().strip() in FOOD_RELATED_INDUSTRIES


def _format_fda_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _parse_fda_date(date_str: str) -> datetime | None:
    if not date_str or len(date_str) < 8:
        return None
    try:
        return datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except (ValueError, IndexError):
        return None


def _simplify_recall_reason(reason: str) -> str:
    lower = reason.lower()
    if "undeclared" in lower or "allergen" in lower:
        return "Undeclared allergens"
    if "listeria" in lower:
        return "Listeria contamination"
    if "salmonella" in lower:
        return "Salmonella contamination"
    if "e. coli" in lower or "e.coli" in lower:
        return "E. coli contamination"
    if "foreign" in lower or "metal" in lower or "plastic" in lower:
        return "Foreign material"
    if "mislabel" in lower or "misbranded" in lower:
        return "Mislabeling"
    if "temperature" in lower or "refrigerat" in lower:
        return "Temperature abuse"
    return reason[:50].strip()


async def query_fda_enforcements(state: str) -> FdaData:
    """Query FDA food enforcement API for recall data in a given state."""
    empty = FdaData()
    if not state:
        return empty

    try:
        state_query = state.upper() if len(state) == 2 else state
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        date_from = _format_fda_date(one_year_ago)
        date_to = _format_fda_date(datetime.utcnow())

        search_query = f'state:"{state_query}"+AND+report_date:[{date_from}+TO+{date_to}]'
        url = f"{FDA_BASE_URL}?search={search_query}&limit=100"

        logger.info(f'[FDA] Querying enforcements for state "{state_query}"')

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)

        if response.status_code == 404:
            logger.info(f'[FDA] No enforcement records found for state "{state_query}"')
            return empty
        if response.status_code != 200:
            logger.warning(f"[FDA] API returned {response.status_code}")
            return empty

        data = response.json()
        results = data.get("results", [])
        total = data.get("meta", {}).get("results", {}).get("total", len(results))

        three_months_ago = datetime.utcnow() - timedelta(days=90)
        recent_count = sum(
            1 for r in results
            if (d := _parse_fda_date(r.get("report_date", ""))) and d >= three_months_ago
        )

        reason_counts: dict[str, int] = {}
        for r in results:
            reason = _simplify_recall_reason(r.get("reason_for_recall", ""))
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        top_reasons = [
            f"{reason} ({count})"
            for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])[:5]
        ]

        enforcements = [
            FdaEnforcement(
                recalling_firm=r.get("recalling_firm", ""),
                reason_for_recall=r.get("reason_for_recall", ""),
                classification=r.get("classification", ""),
                report_date=r.get("report_date", ""),
                product_description=r.get("product_description", ""),
            )
            for r in results[:10]
        ]

        logger.info(f'[FDA] Found {total} total recalls, {recent_count} recent for state "{state_query}"')

        return FdaData(
            enforcements=enforcements,
            totalRecalls=total,
            recentRecallCount=recent_count,
            topReasons=top_reasons,
        )
    except Exception as e:
        logger.error(f'[FDA] Query failed for state "{state}": {e}')
        return empty
