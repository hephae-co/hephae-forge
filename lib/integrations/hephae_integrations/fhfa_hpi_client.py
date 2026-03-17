"""FHFA House Price Index client at ZIP code level."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FHFA_HPI_CSV_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_zip5.csv"
FHFA_HPI_XLSX_URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_zip5.xlsx"

# Module-level cache: maps zip_code -> list of yearly records [{year, hpi}, ...]
# Populated once on first call, then reused.
_hpi_cache: dict[str, list[dict[str, Any]]] = {}
_cache_loaded: bool = False


def _classify_wealth_effect(five_year_change_pct: float) -> str:
    """Classify wealth effect based on 5-year cumulative HPI change."""
    if five_year_change_pct > 30:
        return "strong"
    if five_year_change_pct < 10:
        return "weak"
    return "moderate"


def _classify_trend(annual_change_pct: float) -> str:
    """Classify trend based on year-over-year HPI change."""
    if annual_change_pct > 2.0:
        return "appreciating"
    if annual_change_pct < -2.0:
        return "declining"
    return "stable"


async def _load_hpi_data() -> None:
    """Download and parse the FHFA HPI ZIP-level dataset into the module cache."""
    global _cache_loaded

    if _cache_loaded:
        return

    logger.info("[FHFA_HPI] Downloading HPI ZIP-level dataset")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(FHFA_HPI_CSV_URL)

        if response.status_code != 200:
            logger.warning(
                f"[FHFA_HPI] CSV download returned {response.status_code}, "
                f"trying XLSX fallback is not supported — aborting"
            )
            _cache_loaded = True
            return

        text = response.text
        reader = csv.DictReader(io.StringIO(text))

        for row in reader:
            # Expected columns: Five-Digit ZIP Code, Year, Annual Change (%),
            # HPI, HPI with 1990 base, HPI with 2000 base
            zip_code = row.get("Five-Digit ZIP Code", "").strip()
            if not zip_code or len(zip_code) != 5:
                continue

            try:
                year = int(row.get("Year", "0"))
            except (ValueError, TypeError):
                continue

            # Try multiple possible column names for HPI value
            hpi_val = None
            for col_name in ("HPI", "HPI with 1990 base", "HPI with 2000 base",
                             "Index (NSA)", "Annual Change (%)"):
                raw = row.get(col_name, "").strip()
                if raw and raw not in (".", ""):
                    try:
                        hpi_val = float(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            if hpi_val is None:
                continue

            # Parse annual change if available
            annual_change = None
            change_raw = row.get("Annual Change (%)", "").strip()
            if change_raw and change_raw not in (".", ""):
                try:
                    annual_change = float(change_raw)
                except (ValueError, TypeError):
                    pass

            _hpi_cache.setdefault(zip_code, []).append({
                "year": year,
                "hpi": hpi_val,
                "annualChange": annual_change,
            })

        # Sort each zip's records by year
        for records in _hpi_cache.values():
            records.sort(key=lambda r: r["year"])

        logger.info(f"[FHFA_HPI] Loaded HPI data for {len(_hpi_cache)} ZIP codes")
        _cache_loaded = True

    except Exception as e:
        logger.error(f"[FHFA_HPI] Failed to download/parse HPI data: {e}")
        _cache_loaded = True


async def query_house_price_index(
    zip_code: str,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query FHFA House Price Index for a given ZIP code.

    Args:
        zip_code: 5-digit ZIP code string.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with zipCode, latestYear, hpi, annualChangePct, trend,
        fiveYearChangePct, and wealthEffect. Returns empty dict if ZIP
        not found in dataset.
    """
    empty: dict[str, Any] = {}

    if not zip_code or len(zip_code.strip()) != 5:
        logger.warning("[FHFA_HPI] Invalid zip code provided")
        return empty

    zip_code = zip_code.strip()

    if cache_reader:
        try:
            cached = await cache_reader("fhfa_hpi", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        await _load_hpi_data()

        records = _hpi_cache.get(zip_code)
        if not records:
            logger.warning(f"[FHFA_HPI] No HPI data for zip={zip_code}")
            return empty

        latest = records[-1]
        latest_year = latest["year"]
        latest_hpi = latest["hpi"]

        # Year-over-year change
        annual_change_pct = 0.0
        if latest.get("annualChange") is not None:
            annual_change_pct = round(latest["annualChange"], 2)
        elif len(records) >= 2:
            prev = records[-2]
            if prev["hpi"] > 0:
                annual_change_pct = round(
                    ((latest_hpi - prev["hpi"]) / prev["hpi"]) * 100, 2
                )

        # Five-year cumulative change
        five_year_change_pct = 0.0
        target_year = latest_year - 5
        five_year_record = None
        for r in records:
            if r["year"] == target_year:
                five_year_record = r
                break
        if five_year_record and five_year_record["hpi"] > 0:
            five_year_change_pct = round(
                ((latest_hpi - five_year_record["hpi"]) / five_year_record["hpi"]) * 100, 2
            )

        trend = _classify_trend(annual_change_pct)
        wealth_effect = _classify_wealth_effect(five_year_change_pct)

        logger.info(
            f"[FHFA_HPI] zip={zip_code}: hpi={latest_hpi:.1f}, "
            f"yoy={annual_change_pct:.1f}%, 5yr={five_year_change_pct:.1f}%, "
            f"trend={trend}, wealth={wealth_effect}"
        )

        result: dict[str, Any] = {
            "zipCode": zip_code,
            "latestYear": latest_year,
            "hpi": round(latest_hpi, 2),
            "annualChangePct": annual_change_pct,
            "trend": trend,
            "fiveYearChangePct": five_year_change_pct,
            "wealthEffect": wealth_effect,
        }

        if cache_writer:
            try:
                await cache_writer("fhfa_hpi", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[FHFA_HPI] Query failed for zip={zip_code}: {e}")
        return empty
