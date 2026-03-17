"""BLS Quarterly Census of Employment and Wages (QCEW) client.

County-level employment, wages, and establishment counts by NAICS industry.
Uses the BLS QCEW CSV API (no key required).

URL pattern: https://data.bls.gov/cew/data/api/{year}/{qtr}/area/{area_fips}.csv
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

QCEW_API_URL = "https://data.bls.gov/cew/data/api"

# Map business types to NAICS codes (2-4 digit)
BUSINESS_TO_NAICS: dict[str, list[str]] = {
    "restaurants": ["722", "7225"],
    "bakeries": ["3118", "722515"],
    "cafes": ["722515"],
    "coffee": ["722515"],
    "pizza": ["722511"],
    "retail": ["44-45", "441", "442", "443", "444", "445", "446", "447", "448", "451", "452", "453"],
    "grocery": ["4451", "445"],
    "salon": ["8121", "812111"],
    "barber": ["812111"],
    "gym": ["71394"],
    "auto repair": ["8111"],
    "laundry": ["8123"],
    "florist": ["4531"],
    "pet store": ["4532"],
}

# County FIPS lookup — for common NJ counties (extend as needed)
# Full mapping would come from HUD crosswalk or BQ geo_us_boundaries
COUNTY_NAME_TO_FIPS: dict[str, str] = {
    "passaic county, nj": "34031",
    "bergen county, nj": "34003",
    "essex county, nj": "34013",
    "hudson county, nj": "34017",
    "morris county, nj": "34027",
    "union county, nj": "34039",
    "middlesex county, nj": "34023",
    "monmouth county, nj": "34025",
    "ocean county, nj": "34029",
    "mercer county, nj": "34021",
    "camden county, nj": "34007",
    "burlington county, nj": "34005",
    "somerset county, nj": "34035",
    "sussex county, nj": "34037",
    "warren county, nj": "34041",
    "hunterdon county, nj": "34019",
    "gloucester county, nj": "34015",
    "atlantic county, nj": "34001",
    "cape may county, nj": "34009",
    "cumberland county, nj": "34011",
    "salem county, nj": "34033",
}


def _resolve_county_fips(county: str, state: str) -> str | None:
    """Resolve county name + state to FIPS code."""
    key = f"{county.lower().strip()}, {state.lower().strip()}"
    fips = COUNTY_NAME_TO_FIPS.get(key)
    if fips:
        return fips
    # Try without "county" suffix
    key_alt = f"{county.lower().strip().replace(' county', '')}, {state.lower().strip()}"
    for k, v in COUNTY_NAME_TO_FIPS.items():
        if key_alt in k:
            return v
    return None


async def query_qcew_employment(
    county: str,
    state: str,
    business_type: str = "",
    year: int = 2024,
    quarter: int = 1,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query BLS QCEW for employment and wage data by county and industry.

    Returns establishment counts, employment levels, and wages for the
    target industry and total private sector in the county.
    """
    empty: dict[str, Any] = {}

    county_fips = _resolve_county_fips(county, state)
    if not county_fips:
        logger.warning(f"[QCEW] Could not resolve FIPS for {county}, {state}")
        return empty

    cache_key = f"{county_fips}-{year}-{quarter}"
    if cache_reader:
        try:
            cached = await cache_reader("qcew", cache_key, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        url = f"{QCEW_API_URL}/{year}/{quarter}/area/{county_fips}.csv"
        logger.info(f"[QCEW] Fetching {county} ({county_fips}) Q{quarter} {year}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)

        if response.status_code != 200:
            # Try previous quarter/year
            if quarter > 1:
                url = f"{QCEW_API_URL}/{year}/{quarter - 1}/area/{county_fips}.csv"
            else:
                url = f"{QCEW_API_URL}/{year - 1}/4/area/{county_fips}.csv"
            response = await client.get(url)
            if response.status_code != 200:
                logger.warning(f"[QCEW] API returned {response.status_code} for {county_fips}")
                return empty

        # Parse CSV
        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        if not rows:
            return empty

        # Extract total private sector data
        private_total = None
        industry_rows: list[dict[str, Any]] = []

        normalized_type = business_type.lower().strip().rstrip("s")
        target_naics = BUSINESS_TO_NAICS.get(normalized_type, [])

        for row in rows:
            own_code = row.get("own_code", "")
            naics = row.get("industry_code", "")

            # Total private sector (own_code=5, industry=10 = total)
            if own_code == "5" and naics == "10":
                private_total = row

            # Target industry rows
            if own_code == "5" and naics in target_naics:
                industry_rows.append(row)

        result: dict[str, Any] = {
            "countyFips": county_fips,
            "county": county,
            "state": state,
            "year": year,
            "quarter": quarter,
        }

        # Total private sector stats
        if private_total:
            estabs = int(private_total.get("qtrly_estabs", 0) or 0)
            emp = int(private_total.get("month1_emplvl", 0) or 0)
            avg_wage = int(private_total.get("avg_wkly_wage", 0) or 0)
            oty_estabs_chg = private_total.get("oty_qtrly_estabs_pct_chg", "")

            result["totalPrivate"] = {
                "establishments": estabs,
                "employment": emp,
                "avgWeeklyWage": avg_wage,
                "estabsYoYChangePct": float(oty_estabs_chg) if oty_estabs_chg else None,
            }

        # Industry-specific stats
        if industry_rows:
            industry_data = []
            for row in industry_rows:
                estabs = int(row.get("qtrly_estabs", 0) or 0)
                emp = int(row.get("month1_emplvl", 0) or 0)
                avg_wage = int(row.get("avg_wkly_wage", 0) or 0)
                oty_chg = row.get("oty_qtrly_estabs_pct_chg", "")
                industry_data.append({
                    "naicsCode": row.get("industry_code", ""),
                    "industryTitle": row.get("industry_title", "").strip(),
                    "establishments": estabs,
                    "employment": emp,
                    "avgWeeklyWage": avg_wage,
                    "estabsYoYChangePct": float(oty_chg) if oty_chg else None,
                })
            result["industryData"] = industry_data

            # Generate highlights
            highlights = []
            for ind in industry_data:
                if ind.get("estabsYoYChangePct") is not None:
                    chg = ind["estabsYoYChangePct"]
                    direction = "grew" if chg > 0 else "shrank"
                    highlights.append(
                        f"{ind['industryTitle']}: {ind['establishments']} establishments "
                        f"({direction} {abs(chg):.1f}% YoY), "
                        f"{ind['employment']} employees, avg ${ind['avgWeeklyWage']}/week"
                    )
            result["highlights"] = highlights

        logger.info(f"[QCEW] Got data for {county_fips}: {len(industry_rows)} industry rows")

        if cache_writer:
            try:
                await cache_writer("qcew", cache_key, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[QCEW] Query failed for {county_fips}: {e}")
        return empty
