"""
BusinessContext — shared context layer for all capability agents.

Assembles all data needed for capability agents: identity, admin research,
pre-fetched market data. Cached per-slug for 1 hour.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from hephae_db.firestore.businesses import generate_slug, read_business
from hephae_db.context.admin_data import get_zipcode_report, get_area_research_for_zip

logger = logging.getLogger(__name__)

_CONTEXT_TTL_S = 3600
_context_store: dict[str, tuple[BusinessContext, float]] = {}


def _get_cached(slug: str) -> Optional[BusinessContext]:
    entry = _context_store.get(slug)
    if entry and (time.time() - entry[1]) < _CONTEXT_TTL_S:
        return entry[0]
    _context_store.pop(slug, None)
    return None


def _store_cached(ctx: BusinessContext) -> None:
    _context_store[ctx.slug] = (ctx, time.time())


def clear_context_cache(slug: str | None = None) -> None:
    """Clear cached context. If slug is None, clear all."""
    if slug:
        _context_store.pop(slug, None)
    else:
        _context_store.clear()


@dataclass
class BusinessContext:
    """All data needed for capability agents, assembled once per business."""

    slug: str
    identity: dict[str, Any]
    zip_code: str | None = None

    zipcode_research: dict | None = None
    area_research: dict | None = None
    food_pricing_context: dict | None = None
    admin_insights: dict | None = None

    cpi_data: dict | None = None
    fred_data: dict | None = None
    commodity_prices: dict[str, dict] = field(default_factory=dict)

    gemini_cache_name: str | None = None
    created_at: float = 0.0

    @property
    def name(self) -> str:
        return self.identity.get("name", "")

    @property
    def address(self) -> str | None:
        return self.identity.get("address")

    @property
    def coordinates(self) -> dict | None:
        return self.identity.get("coordinates")

    @property
    def official_url(self) -> str:
        return self.identity.get("officialUrl", "")

    @property
    def competitors(self) -> list[dict]:
        return self.identity.get("competitors") or []

    @property
    def hours(self) -> str | None:
        return self.identity.get("hours")

    @property
    def has_admin_data(self) -> bool:
        return bool(self.zipcode_research or self.area_research)

    def get_cpi(self) -> dict | None:
        if self.food_pricing_context:
            return self.food_pricing_context.get("blsCpiData") or self.food_pricing_context
        if self.area_research:
            intel = self.area_research.get("industryIntelligence") or {}
            if intel.get("blsCpiData"):
                return intel["blsCpiData"]
        return self.cpi_data

    def get_commodity_data(self) -> dict | None:
        if self.food_pricing_context:
            return self.food_pricing_context.get("usdaPriceData") or self.food_pricing_context
        if self.area_research:
            intel = self.area_research.get("industryIntelligence") or {}
            if intel.get("usdaPriceData"):
                return intel["usdaPriceData"]
        return self.commodity_prices if self.commodity_prices else None

    def get_fred(self) -> dict | None:
        return self.fred_data

    def to_prompt_context(self) -> str:
        """Serialize to structured text for agent prompts / Gemini cache."""
        import json

        sections = []
        sections.append(f"## Business Identity\n{json.dumps(self.identity, indent=2, default=str)}")

        if self.zipcode_research:
            sections.append(f"## Zip Code Research (Admin)\n{json.dumps(self.zipcode_research, indent=2, default=str)}")

        if self.area_research:
            sections.append(f"## Area Research (Admin)\n{json.dumps(self.area_research, indent=2, default=str)}")

        if self.food_pricing_context:
            sections.append(f"## Food Pricing Context\n{json.dumps(self.food_pricing_context, indent=2, default=str)}")

        cpi = self.get_cpi()
        if cpi and not self.food_pricing_context:
            sections.append(f"## CPI Data (Pre-fetched)\n{json.dumps(cpi, indent=2, default=str)}")

        fred = self.get_fred()
        if fred:
            sections.append(f"## FRED Economic Indicators\n{json.dumps(fred, indent=2, default=str)}")

        if self.commodity_prices and not self.food_pricing_context:
            sections.append(f"## Commodity Prices (Pre-fetched)\n{json.dumps(self.commodity_prices, indent=2, default=str)}")

        return "\n\n".join(sections)


def _parse_zip_code(address: str | None, stored_zip: str | None = None) -> str | None:
    if stored_zip:
        return stored_zip
    if not address:
        return None
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return match.group(1) if match else None


async def build_business_context(
    identity: dict[str, Any],
    capabilities: list[str] | None = None,
) -> BusinessContext:
    """Build a complete BusinessContext for capability agents.

    1. Reads businesses/{slug} from Firestore
    2. Loads admin data (zipcode_research, area_research) if available
    3. Pre-fetches deterministic market data when admin data is missing
    """
    name = identity.get("name")
    if not name:
        return BusinessContext(slug="unknown", identity=identity, created_at=time.time())

    slug = generate_slug(name)

    cached = _get_cached(slug)
    if cached:
        for k, v in identity.items():
            if v is not None:
                cached.identity[k] = v
        logger.info(f"[BusinessContext] Cache HIT for {slug}")
        return cached

    stored = read_business(slug)
    if stored:
        merged = {**stored}
        for k, v in identity.items():
            if v is not None:
                merged[k] = v
        for key in ("createdAt", "updatedAt", "latestOutputs", "crm"):
            merged.pop(key, None)
    else:
        merged = identity

    zip_code = _parse_zip_code(
        merged.get("address"),
        stored.get("zipCode") if stored else None,
    )

    food_pricing_context = (stored or {}).get("foodPricingContext")
    admin_insights = (stored or {}).get("insights")

    zipcode_report = None
    area_report = None
    if zip_code:
        zip_task = get_zipcode_report(zip_code)
        area_task = get_area_research_for_zip(zip_code)
        results = await asyncio.gather(zip_task, area_task, return_exceptions=True)
        if not isinstance(results[0], Exception):
            zipcode_report = results[0]
        else:
            logger.warning(f"[BusinessContext] zipcode_research read failed: {results[0]}")
        if not isinstance(results[1], Exception):
            area_report = results[1]
        else:
            logger.warning(f"[BusinessContext] area_research read failed: {results[1]}")

    caps = set(capabilities or ["margin", "traffic", "seo", "competitive", "marketing"])
    cpi_data = None
    fred_data = None
    commodity_prices: dict[str, dict] = {}

    needs_market_data = "margin" in caps or "surgery" in caps
    has_admin_market_data = bool(food_pricing_context) or bool(
        area_report and (area_report.get("industryIntelligence") or {}).get("blsCpiData")
    )

    if needs_market_data and not has_admin_market_data:
        logger.info(f"[BusinessContext] No admin market data for {slug} — pre-fetching BLS/FRED")
        try:
            from hephae_capabilities.market_data import (
                fetch_cpi_data,
                fetch_commodity_prices,
                fetch_fred_indicators,
            )

            region = _infer_region(merged.get("address", ""))

            prefetch_tasks = {
                "cpi": fetch_cpi_data(region),
                "fred": fetch_fred_indicators("UNRATE"),
                "eggs": fetch_commodity_prices("eggs"),
                "beef": fetch_commodity_prices("beef"),
                "dairy": fetch_commodity_prices("dairy"),
                "poultry": fetch_commodity_prices("poultry"),
            }

            keys = list(prefetch_tasks.keys())
            values = await asyncio.gather(*prefetch_tasks.values(), return_exceptions=True)

            for k, v in zip(keys, values):
                if isinstance(v, Exception):
                    logger.warning(f"[BusinessContext] Pre-fetch {k} failed: {v}")
                    continue
                if k == "cpi":
                    cpi_data = v
                elif k == "fred":
                    fred_data = v
                else:
                    commodity_prices[k] = v

        except Exception as e:
            logger.error(f"[BusinessContext] Market data pre-fetch failed: {e}")

    ctx = BusinessContext(
        slug=slug,
        identity=merged,
        zip_code=zip_code,
        zipcode_research=zipcode_report,
        area_research=area_report,
        food_pricing_context=food_pricing_context,
        admin_insights=admin_insights,
        cpi_data=cpi_data,
        fred_data=fred_data,
        commodity_prices=commodity_prices,
        created_at=time.time(),
    )

    _store_cached(ctx)

    admin_tag = "with admin data" if ctx.has_admin_data else "no admin data"
    market_tag = "admin market data" if has_admin_market_data else (
        f"pre-fetched {len(commodity_prices)} commodities" if commodity_prices else "no market data"
    )
    logger.info(f"[BusinessContext] Built for {slug} ({admin_tag}, {market_tag})")

    return ctx


def _infer_region(address: str) -> str:
    """Infer BLS CPI region from address string."""
    lc = address.lower() if address else ""
    if re.search(r"\bfl\b|\btx\b|miami|austin|south carolina|georgia|alabama|tennessee|louisiana|north carolina", lc):
        return "South"
    if re.search(r"\bil\b|chicago|midwest|ohio|michigan|indiana|wisconsin|minnesota", lc):
        return "Midwest"
    if re.search(r"\bca\b|california|oregon|washington|nevada|arizona|colorado|utah", lc):
        return "West"
    return "Northeast"
