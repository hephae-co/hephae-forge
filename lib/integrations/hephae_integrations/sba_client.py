"""SBA loan data client from data.sba.gov (PPP/7a FOIA dataset)."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SBA_SODA_URL = "https://data.sba.gov/resource/fljg-xm4t.json"

# National average PPP loans per zip code (~30 over program lifetime).
# Used as a baseline for newBusinessSignal scoring.
_NATIONAL_AVG_ANNUAL_LOANS = 30


def _classify_new_business_signal(loan_count: int) -> str:
    """Classify new-business signal based on loan volume vs national average."""
    if loan_count >= _NATIONAL_AVG_ANNUAL_LOANS * 1.5:
        return "high"
    if loan_count >= _NATIONAL_AVG_ANNUAL_LOANS * 0.5:
        return "medium"
    return "low"


def _extract_top_industries(loans: list[dict[str, Any]], limit: int = 5) -> list[str]:
    """Extract most common NAICS sectors from loan records."""
    sector_counter: Counter[str] = Counter()
    for loan in loans:
        naics = loan.get("naicscode", "") or loan.get("naics_code", "")
        if naics and len(str(naics)) >= 2:
            sector_counter[str(naics)[:2]] += 1
    return [sector for sector, _ in sector_counter.most_common(limit)]


async def query_sba_loans(
    zip_code: str,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query SBA SODA API for PPP loan data by zip code.

    Args:
        zip_code: 5-digit ZIP code to query.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with recentLoans, totalAmount, topIndustries, avgLoanSize,
        newBusinessSignal.
    """
    empty: dict[str, Any] = {
        "recentLoans": 0,
        "totalAmount": 0.0,
        "topIndustries": [],
        "avgLoanSize": 0.0,
        "newBusinessSignal": "low",
    }

    if not zip_code or not zip_code.strip().isdigit():
        logger.warning("[SBA] Invalid zip_code provided")
        return empty

    zip_code = zip_code.strip()[:5]

    if cache_reader:
        try:
            cached = await cache_reader("sba", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        one_year_ago = datetime.utcnow() - timedelta(days=365)
        date_str = one_year_ago.strftime("%Y-%m-%dT00:00:00.000")

        params: dict[str, str] = {
            "$where": f"zip='{zip_code}' AND dateapproved > '{date_str}'",
            "$limit": "200",
            "$order": "dateapproved DESC",
        }

        logger.info(f"[SBA] Querying PPP loans for zip={zip_code}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(SBA_SODA_URL, params=params)

        if response.status_code != 200:
            logger.warning(f"[SBA] API returned {response.status_code}")
            return empty

        loans = response.json()
        if not isinstance(loans, list):
            logger.warning("[SBA] Unexpected response format")
            return empty

        # Calculate aggregates
        total_amount = 0.0
        for loan in loans:
            amount_str = str(loan.get("currentapprovalamount", "") or loan.get("initialapprovalamount", "0"))
            try:
                total_amount += float(amount_str)
            except (ValueError, TypeError):
                pass

        loan_count = len(loans)
        avg_loan_size = round(total_amount / loan_count, 2) if loan_count > 0 else 0.0
        top_industries = _extract_top_industries(loans)
        signal = _classify_new_business_signal(loan_count)

        logger.info(f"[SBA] Found {loan_count} loans in zip={zip_code}, total=${total_amount:,.0f}")

        result: dict[str, Any] = {
            "recentLoans": loan_count,
            "totalAmount": round(total_amount, 2),
            "topIndustries": top_industries,
            "avgLoanSize": avg_loan_size,
            "newBusinessSignal": signal,
        }

        if cache_writer:
            try:
                await cache_writer("sba", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[SBA] Query failed for zip={zip_code}: {e}")
        return empty
