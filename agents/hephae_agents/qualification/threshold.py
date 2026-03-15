"""Dynamic threshold computation — adapts qualification bar based on market context."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

BASE_THRESHOLD = 40


def compute_dynamic_threshold(research_context: dict[str, Any] | None) -> int:
    """Compute the qualification threshold based on area/sector research context."""
    if not research_context:
        return BASE_THRESHOLD

    threshold = BASE_THRESHOLD

    area = research_context.get("area_summary") or {}
    competitive = area.get("competitiveLandscape") or {}
    saturation = competitive.get("saturationLevel", "moderate")
    biz_count = competitive.get("existingBusinessCount", 0)

    if saturation == "saturated" or biz_count >= 40:
        threshold = 60
    elif saturation == "high" or biz_count >= 20:
        threshold = 50
    elif saturation == "low" or biz_count < 10:
        threshold = 30

    market_opp = area.get("marketOpportunity") or {}
    opp_score = market_opp.get("score", 0)
    if opp_score > 70:
        threshold -= 10

    threshold = max(20, min(70, threshold))

    logger.info(
        f"[Threshold] Dynamic threshold={threshold} "
        f"(saturation={saturation}, bizCount={biz_count}, oppScore={opp_score})"
    )
    return threshold


def extract_research_context(
    area_research: dict[str, Any] | None = None,
    zipcode_research: dict[str, Any] | None = None,
    sector_research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract research signals needed for threshold computation."""
    ctx: dict[str, Any] = {}

    if area_research:
        summary = area_research.get("summary") or area_research
        if isinstance(summary, dict):
            ctx["area_summary"] = summary

    if zipcode_research:
        report = zipcode_research.get("report") or zipcode_research
        sections = report.get("sections") if isinstance(report, dict) else None
        if sections and isinstance(sections, dict):
            demo = sections.get("demographics")
            if demo:
                ctx["demographics"] = demo

    if sector_research:
        summary = sector_research.get("summary") or sector_research
        if isinstance(summary, dict):
            ctx["sector_summary"] = summary

    return ctx
