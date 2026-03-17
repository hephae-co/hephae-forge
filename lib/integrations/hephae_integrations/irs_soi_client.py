"""IRS Statistics of Income (SOI) client for ZIP-level income data."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

IRS_SOI_CSV_URL = "https://www.irs.gov/pub/irs-soi/22zpallnoagi.csv"

# Module-level cache: maps zip_code -> row dict with numeric fields
_soi_cache: dict[str, dict[str, float]] = {}
_cache_loaded: bool = False


def _safe_float(value: str) -> float:
    """Parse a string to float, returning 0.0 on failure."""
    if not value:
        return 0.0
    try:
        return float(value.strip().replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _classify_entrepreneurship(self_employment_rate: float) -> str:
    """Classify entrepreneurship signal based on self-employment rate."""
    if self_employment_rate > 15:
        return "high"
    if self_employment_rate < 5:
        return "low"
    return "moderate"


def _classify_spending_power(avg_agi: float) -> str:
    """Classify spending power based on average adjusted gross income."""
    if avg_agi > 80000:
        return "high"
    if avg_agi < 40000:
        return "low"
    return "moderate"


async def _load_soi_data() -> None:
    """Download and parse the IRS SOI ZIP-level dataset into the module cache."""
    global _cache_loaded

    if _cache_loaded:
        return

    logger.info("[IRS_SOI] Downloading IRS SOI ZIP-level dataset")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(IRS_SOI_CSV_URL)

        if response.status_code != 200:
            logger.warning(f"[IRS_SOI] CSV download returned {response.status_code}")
            _cache_loaded = True
            return

        text = response.text
        reader = csv.DictReader(io.StringIO(text))

        for row in reader:
            # The ZIP code column may be named ZIPCODE, zipcode, or STATE+zipcode
            zip_code = ""
            for col_name in ("ZIPCODE", "zipcode", "Zip Code", "ZIP"):
                val = row.get(col_name, "").strip()
                if val and len(val) == 5 and val.isdigit():
                    zip_code = val
                    break

            if not zip_code:
                # Try zero-padded: some ZIPs may be numeric without leading zeros
                for col_name in ("ZIPCODE", "zipcode", "Zip Code", "ZIP"):
                    val = row.get(col_name, "").strip()
                    if val:
                        try:
                            zip_code = str(int(val)).zfill(5)
                            if len(zip_code) == 5:
                                break
                            zip_code = ""
                        except (ValueError, TypeError):
                            continue

            if not zip_code:
                continue

            _soi_cache[zip_code] = {
                "N1": _safe_float(row.get("N1", row.get("n1", ""))),
                "A00100": _safe_float(row.get("A00100", row.get("a00100", ""))),
                "A00200": _safe_float(row.get("A00200", row.get("a00200", ""))),
                "N00900": _safe_float(row.get("N00900", row.get("n00900", ""))),
                "A00900": _safe_float(row.get("A00900", row.get("a00900", ""))),
                "N59660": _safe_float(row.get("N59660", row.get("n59660", ""))),
            }

        logger.info(f"[IRS_SOI] Loaded SOI data for {len(_soi_cache)} ZIP codes")
        _cache_loaded = True

    except Exception as e:
        logger.error(f"[IRS_SOI] Failed to download/parse SOI data: {e}")
        _cache_loaded = True


async def query_zip_income(
    zip_code: str,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query IRS Statistics of Income for a given ZIP code.

    Args:
        zip_code: 5-digit ZIP code string.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with zipCode, taxYear, totalReturns, avgAGI, avgSalary,
        selfEmploymentRate, selfEmploymentAvgIncome, eitcRate,
        entrepreneurshipSignal, and spendingPower. Returns empty dict
        if ZIP not found in dataset.
    """
    empty: dict[str, Any] = {}

    if not zip_code or len(zip_code.strip()) != 5:
        logger.warning("[IRS_SOI] Invalid zip code provided")
        return empty

    zip_code = zip_code.strip()

    if cache_reader:
        try:
            cached = await cache_reader("irs_soi", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        await _load_soi_data()

        row = _soi_cache.get(zip_code)
        if not row:
            logger.warning(f"[IRS_SOI] No SOI data for zip={zip_code}")
            return empty

        n1 = row["N1"]
        if n1 <= 0:
            logger.warning(f"[IRS_SOI] Zero returns for zip={zip_code}")
            return empty

        a00100 = row["A00100"]
        a00200 = row["A00200"]
        n00900 = row["N00900"]
        a00900 = row["A00900"]
        n59660 = row["N59660"]

        total_returns = int(n1)
        avg_agi = round((a00100 * 1000) / n1, 2)
        avg_salary = round((a00200 * 1000) / n1, 2)
        self_employment_rate = round((n00900 / n1) * 100, 2) if n1 > 0 else 0.0
        self_employment_avg_income = (
            round((a00900 * 1000) / n00900, 2) if n00900 > 0 else 0.0
        )
        eitc_rate = round((n59660 / n1) * 100, 2) if n1 > 0 else 0.0

        entrepreneurship_signal = _classify_entrepreneurship(self_employment_rate)
        spending_power = _classify_spending_power(avg_agi)

        logger.info(
            f"[IRS_SOI] zip={zip_code}: returns={total_returns}, "
            f"avgAGI=${avg_agi:,.0f}, selfEmp={self_employment_rate:.1f}%, "
            f"eitc={eitc_rate:.1f}%, entrepreneur={entrepreneurship_signal}, "
            f"spending={spending_power}"
        )

        result: dict[str, Any] = {
            "zipCode": zip_code,
            "taxYear": 2022,
            "totalReturns": total_returns,
            "avgAGI": avg_agi,
            "avgSalary": avg_salary,
            "selfEmploymentRate": self_employment_rate,
            "selfEmploymentAvgIncome": self_employment_avg_income,
            "eitcRate": eitc_rate,
            "entrepreneurshipSignal": entrepreneurship_signal,
            "spendingPower": spending_power,
        }

        if cache_writer:
            try:
                await cache_writer("irs_soi", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[IRS_SOI] Query failed for zip={zip_code}: {e}")
        return empty
