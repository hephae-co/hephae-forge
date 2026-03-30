"""Shared utility for building local facts and intel from cached data signals.

Used by:
- business_overview/runner.py (_build_dashboard)
- synthesis/zip_digest.py (ZipDataLoader)
"""

from __future__ import annotations

from typing import Any


def build_local_facts(
    irs: dict[str, Any],
    weather: dict[str, Any],
    census: dict[str, Any],
    research_facts: list[str] | None = None,
) -> list[str]:
    """Build specific, surprising local facts from cached signals.

    Returns up to 6 facts as plain-text strings.
    """
    facts: list[str] = []

    if irs.get("avgAGI"):
        try:
            facts.append(f"Avg household income ${int(irs['avgAGI']):,} (IRS)")
        except (ValueError, TypeError):
            pass
    if irs.get("selfEmploymentRate"):
        try:
            rate = float(irs["selfEmploymentRate"])
            if rate > 10:
                facts.append(f"{rate}% are self-employed — fellow business owners")
        except (ValueError, TypeError):
            pass
    if census.get("medianRent"):
        try:
            facts.append(f"Median rent ${int(census['medianRent']):,}")
        except (ValueError, TypeError):
            pass
    if census.get("medianHomeValue"):
        try:
            facts.append(f"Median home value ${int(census['medianHomeValue']):,}")
        except (ValueError, TypeError):
            pass
    if census.get("vacancyRate"):
        try:
            vr = float(census["vacancyRate"])
            label = "very tight market" if vr < 5 else "moderate availability" if vr < 10 else "high vacancy"
            facts.append(f"{vr}% vacancy rate — {label}")
        except (ValueError, TypeError):
            pass
    if weather.get("outdoorFavorability"):
        fav = str(weather["outdoorFavorability"]).lower()
        if fav in ("high", "very high"):
            facts.append("Great outdoor conditions this week — expect foot traffic boost")
        elif fav in ("low", "very low"):
            facts.append("Poor outdoor conditions — expect lower walk-in traffic")

    # Append research-derived facts (deduplicated)
    for fact in (research_facts or []):
        if fact and fact not in facts:
            facts.append(fact)

    return facts[:6]


def build_local_intel(
    irs: dict[str, Any],
    census: dict[str, Any],
) -> dict[str, str]:
    """Build local intel summary map for dashboard pills."""
    intel: dict[str, str] = {}
    if irs.get("spendingPower"):
        intel["spendingPower"] = str(irs["spendingPower"])
    if census.get("priceSensitivity"):
        intel["priceSensitivity"] = str(census["priceSensitivity"])
    return intel
