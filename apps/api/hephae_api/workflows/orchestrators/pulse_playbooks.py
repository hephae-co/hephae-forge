"""Pulse playbook registry — deterministic strategy matching + impact computation.

Playbooks are static strategies triggered by specific signal conditions.
No vector search or RAG — just Python dict matching.

Pre-computed impact multipliers are Python arithmetic injected into
session.state for the synthesis LLM. The LLM writes narrative, not math.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Playbook Registry — ~20 playbooks, built over time
# ---------------------------------------------------------------------------

PLAYBOOKS: dict[str, dict[str, Any]] = {
    "dairy_margin_swap": {
        "trigger_conditions": {"dairy_yoy_pct": (">", 8), "poultry_yoy_pct": ("<", 0)},
        "play": (
            "Shift daily specials from cream/cheese-heavy dishes to grilled protein. "
            "Dairy is up {dairy_yoy_pct:.1f}% YoY while poultry is down {poultry_yoy_pct:.1f}%. "
            "This swap preserves margins without changing menu prices."
        ),
        "category": "menu_engineering",
        "business_types": ["food"],
    },
    "competitor_delivery_wave": {
        "trigger_conditions": {"delivery_adoption_pct": (">", 0.65)},
        "play": (
            "Launch delivery with a first-week promo targeting unserved demand. "
            "{delivery_adoption_pct:.0%} of local competitors now offer delivery — "
            "staying offline risks losing the convenience segment entirely."
        ),
        "category": "competitive",
        "business_types": ["food", "retail"],
    },
    "construction_spillover": {
        "trigger_conditions": {"road_closure_active": ("==", True)},
        "play": (
            "Capture foot traffic spillover from {closed_street} closure with sidewalk signage "
            "on parallel streets. Construction typically lasts {duration_weeks} weeks."
        ),
        "category": "local_event",
        "business_types": ["all"],
    },
    "price_sensitivity_premium": {
        "trigger_conditions": {"median_income_3yr_change_pct": (">", 5)},
        "play": (
            "Area income rose {median_income_3yr_change_pct:.1f}% over 3 years. "
            "Test premium menu items or service tiers — the market can absorb higher prices."
        ),
        "category": "pricing",
        "business_types": ["all"],
    },
    "new_competitor_alert": {
        "trigger_conditions": {"competitor_delta_3mo": (">", 2)},
        "play": (
            "{competitor_delta_3mo} new competitors opened in the last 3 months. "
            "Differentiate on experience/quality or launch a loyalty program to retain regulars."
        ),
        "category": "competitive",
        "business_types": ["all"],
    },
    "weather_event_boost": {
        "trigger_conditions": {
            "weather_traffic_modifier": (">", -0.05),
            "catalyst_traffic_modifier": (">", 0.15),
        },
        "play": (
            "Good weather + local events this week yield a net +{net_traffic_delta:.0%} "
            "traffic modifier. Staff up and stock perishables accordingly."
        ),
        "category": "operations",
        "business_types": ["all"],
    },
    "weather_rain_prep": {
        "trigger_conditions": {"weather_traffic_modifier": ("<", -0.10)},
        "play": (
            "Forecast predicts {weather_traffic_modifier:.0%} traffic impact from bad weather. "
            "Push delivery/takeout promotions and reduce fresh inventory orders."
        ),
        "category": "operations",
        "business_types": ["food"],
    },
    "sba_formation_surge": {
        "trigger_conditions": {"sba_loan_delta_pct": (">", 25)},
        "play": (
            "SBA loan approvals in this zip are up {sba_loan_delta_pct:.0f}% — new businesses "
            "are entering the area. This means more competition but also a growing commercial district."
        ),
        "category": "competitive",
        "business_types": ["all"],
    },
    "fda_recall_alert": {
        "trigger_conditions": {"fda_recent_recall_count": (">", 2)},
        "play": (
            "{fda_recent_recall_count} FDA recalls in the last 3 months for your state. "
            "Audit your supplier chain against the recalled items and post your food safety "
            "practices on social media for trust building."
        ),
        "category": "compliance",
        "business_types": ["food"],
    },
    "trending_demand_gap": {
        "trigger_conditions": {"trending_gap_detected": ("==", True)},
        "play": (
            "Rising search interest for '{trending_term}' but low local supply. "
            "Consider adding this to your offering before competitors fill the gap."
        ),
        "category": "demand",
        "business_types": ["all"],
    },
}


def _eval_condition(value: Any, operator: str, threshold: Any) -> bool:
    """Evaluate a single trigger condition."""
    if value is None:
        return False
    try:
        if operator == ">":
            return float(value) > float(threshold)
        elif operator == "<":
            return float(value) < float(threshold)
        elif operator == ">=":
            return float(value) >= float(threshold)
        elif operator == "<=":
            return float(value) <= float(threshold)
        elif operator == "==":
            return value == threshold
        elif operator == "in":
            return float(value) in [float(t) for t in threshold]
        return False
    except (ValueError, TypeError):
        return False


def match_playbooks(
    pre_computed: dict[str, Any],
    signals: dict[str, Any] | None = None,
    business_type: str = "",
) -> list[dict[str, Any]]:
    """Evaluate trigger conditions against pre-computed values.

    Returns list of matched playbooks with variables filled in.
    """
    matched: list[dict[str, Any]] = []

    for name, playbook in PLAYBOOKS.items():
        # Check business type filter — playbook applies if ANY listed type matches
        biz_types = playbook.get("business_types", ["all"])
        if "all" not in biz_types:
            from hephae_api.workflows.orchestrators.industry_plugins import is_food_business
            type_match = False
            if "food" in biz_types and is_food_business(business_type):
                type_match = True
            if "retail" in biz_types and business_type.lower() in (
                "retail", "clothing", "boutique", "gift shop", "hardware",
                "electronics", "bookstore", "pet store", "florist",
            ):
                type_match = True
            if "beauty" in biz_types and business_type.lower() in (
                "salons", "salon", "spas", "spa", "barbers", "barber",
                "nail salon", "beauty", "wellness",
            ):
                type_match = True
            if "service" in biz_types and business_type.lower() in (
                "auto repair", "laundry", "dry cleaning", "fitness", "gym",
                "tutoring", "daycare", "veterinary", "vet",
            ):
                type_match = True
            if not type_match:
                continue

        # Evaluate all trigger conditions
        conditions = playbook.get("trigger_conditions", {})
        all_met = True
        for key, (op, threshold) in conditions.items():
            if not _eval_condition(pre_computed.get(key), op, threshold):
                all_met = False
                break

        if all_met:
            # Fill variables into play text
            try:
                play_text = playbook["play"].format(**pre_computed)
            except (KeyError, ValueError):
                play_text = playbook["play"]

            matched.append({
                "name": name,
                "category": playbook.get("category", "general"),
                "play": play_text,
            })

    logger.info(f"[Playbooks] Matched {len(matched)}/{len(PLAYBOOKS)} playbooks")
    return matched


def compute_impact_multipliers(signals: dict[str, Any]) -> dict[str, Any]:
    """Compute pre-computed impact numbers from raw signals.

    These are Python arithmetic — NOT LLM math. The LLM uses these
    as facts in its narrative.

    Returns dict of named multipliers injected into session.state.
    """
    impact: dict[str, Any] = {}

    # BLS CPI price deltas
    price_deltas = signals.get("priceDeltas", [])
    for delta in price_deltas:
        label = delta.get("label", "").lower().replace(" ", "_").replace("/", "_")
        if delta.get("yoyPctChange") is not None:
            impact[f"{label}_yoy_pct"] = round(delta["yoyPctChange"], 2)
        if delta.get("momPctChange") is not None:
            impact[f"{label}_mom_pct"] = round(delta["momPctChange"], 2)

    # Common food categories
    for delta in price_deltas:
        label_lower = delta.get("label", "").lower()
        if "dairy" in label_lower and delta.get("yoyPctChange") is not None:
            impact["dairy_yoy_pct"] = round(delta["yoyPctChange"], 2)
        if "poultry" in label_lower and delta.get("yoyPctChange") is not None:
            impact["poultry_yoy_pct"] = round(delta["yoyPctChange"], 2)

    # OSM business density
    osm = signals.get("osmDensity", {})
    if osm:
        impact["competitor_count"] = osm.get("totalBusinesses", 0)

    # Census demographics
    census = signals.get("censusDemographics", {})
    if census:
        impact["median_income"] = census.get("medianHouseholdIncome", 0)
        impact["population"] = census.get("totalPopulation", 0)
        impact["poverty_rate"] = census.get("povertyRate", 0)

    # IRS income
    irs = signals.get("irsIncome", {})
    if irs:
        impact["avg_agi"] = irs.get("avgAGI", 0)
        impact["self_employment_rate"] = irs.get("selfEmploymentRate", 0)

    # SBA loans
    sba = signals.get("sbaLoans", {})
    if sba:
        impact["sba_recent_loans"] = sba.get("recentLoans", 0)

    # FDA recalls
    fda = signals.get("fdaRecalls", {})
    if fda:
        impact["fda_recent_recall_count"] = fda.get("recentRecallCount", 0)

    # Weather traffic modifier (simple heuristic)
    weather = signals.get("weather", {})
    if weather and weather.get("forecast"):
        rain_days = sum(
            1 for p in weather["forecast"][:7]
            if "rain" in p.get("shortForecast", "").lower()
            or "shower" in p.get("shortForecast", "").lower()
        )
        impact["weather_traffic_modifier"] = round(-0.05 * rain_days, 2)

    # Event traffic modifier — from govtIntel (planning/infra) and eventsResearch (weekly events)
    govt = signals.get("govtIntel", {})
    events = signals.get("eventsResearch", {})
    infra_count = 0
    if isinstance(govt, dict):
        infra_count = len([
            c for c in govt.get("catalysts", [])
            if c.get("type") in ("Development", "Infrastructure")
        ])
    event_count = len(events.get("events", [])) if isinstance(events, dict) else 0
    if infra_count or event_count:
        impact["catalyst_traffic_modifier"] = round(0.10 * min(infra_count + event_count, 3), 2)

    # Net traffic delta
    weather_mod = impact.get("weather_traffic_modifier", 0)
    event_mod = impact.get("catalyst_traffic_modifier", 0)
    impact["net_traffic_delta"] = round(weather_mod + event_mod, 2)

    # FHFA house prices
    hpi = signals.get("housePriceIndex", {})
    if hpi:
        impact["hpi_annual_change_pct"] = hpi.get("annualChangePct", 0)

    # QCEW employment
    qcew = signals.get("qcewEmployment", {})
    if qcew:
        tp = qcew.get("totalPrivate", {})
        if tp.get("estabsYoYChangePct") is not None:
            impact["establishments_yoy_change_pct"] = tp["estabsYoYChangePct"]

    return impact


# ---------------------------------------------------------------------------
# IndustryConfig playbook evaluator
# ---------------------------------------------------------------------------

_TRIGGER_RE = re.compile(r'^(\S+)\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)$')
_IN_RE = re.compile(r'^(\S+)\s+in\s+\[([^\]]+)\]$')


def _parse_trigger(trigger: str) -> tuple[str, str, Any] | None:
    """Parse a single trigger expression into (var, op, value).

    Supports:
    - Simple comparison: 'milk_mom_pct > 1.5'
    - List membership:   'month in [3, 4, 5]'
    """
    trigger = trigger.strip()
    m = _IN_RE.match(trigger)
    if m:
        var = m.group(1)
        try:
            items = [float(x.strip()) for x in m.group(2).split(",")]
            return var, "in", items
        except ValueError:
            return None
    m = _TRIGGER_RE.match(trigger)
    if not m:
        return None
    var, op, val_str = m.groups()
    try:
        return var, op, float(val_str)
    except ValueError:
        return var, op, val_str


def _evaluate_trigger(trigger: str, impact: dict[str, Any]) -> bool:
    """Evaluate a trigger string, supporting compound 'and' expressions."""
    parts = re.split(r'\s+and\s+', trigger, flags=re.IGNORECASE)
    for part in parts:
        parsed = _parse_trigger(part.strip())
        if parsed is None:
            logger.warning(f"[Playbooks] Could not parse trigger part: '{part}'")
            return False
        var, op, threshold = parsed
        if not _eval_condition(impact.get(var), op, threshold):
            return False
    return True


def match_industry_playbooks(
    industry_playbooks: list[dict],
    impact: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate IndustryConfig string-trigger playbooks against pre-computed impact.

    IndustryConfig playbooks use the format:
        {"name": "...", "trigger": "variable > threshold", "play": "..."}

    Triggers support:
    - Simple comparison:  'milk_mom_pct > 1.5'
    - List membership:    'month in [3, 4, 5]'
    - Compound AND:       'dairy_mom_pct > 1.0 and poultry_mom_pct < 0'
    """
    # Inject temporal variables so time-based triggers evaluate correctly
    enriched = {**impact, "month": datetime.now(timezone.utc).month}

    matched: list[dict[str, Any]] = []
    for p in industry_playbooks:
        trigger = p.get("trigger", "").strip()
        if not trigger:
            continue
        if not _evaluate_trigger(trigger, enriched):
            continue
        try:
            play_text = p["play"].format(**enriched)
        except (KeyError, ValueError):
            play_text = p["play"]
        matched.append({
            "name": p.get("name", ""),
            "category": p.get("category", "industry"),
            "play": play_text,
        })

    logger.info(
        f"[Playbooks] Industry playbooks: {len(matched)}/{len(industry_playbooks)} matched"
    )
    return matched
