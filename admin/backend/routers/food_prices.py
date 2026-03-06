"""Food price data endpoints — /api/food-prices."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from backend.lib.bls_client import query_bls_cpi
from backend.lib.usda_client import query_usda_prices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/food-prices", tags=["food-prices"])


@router.get("/cpi")
async def get_food_cpi(
    industry: str = Query("", description="Business type for industry-specific series"),
):
    """Get BLS Consumer Price Index data for food categories."""
    data = await query_bls_cpi(industry)
    return data.model_dump(mode="json")


@router.get("/commodities")
async def get_commodity_prices(
    industry: str = Query("restaurants", description="Business type"),
    state: str = Query("", description="State name or 2-letter code (empty = national)"),
):
    """Get USDA NASS commodity prices for agricultural products."""
    data = await query_usda_prices(industry, state)
    return data.model_dump(mode="json")


@router.get("/summary")
async def get_food_price_summary(
    industry: str = Query("restaurants", description="Business type"),
    state: str = Query("", description="State for USDA data (empty = national)"),
):
    """Get combined food price summary from both BLS CPI and USDA NASS."""
    import asyncio

    bls_task = query_bls_cpi(industry)
    usda_task = query_usda_prices(industry, state)

    bls_data, usda_data = await asyncio.gather(bls_task, usda_task, return_exceptions=True)

    result: dict = {"sources": []}

    if isinstance(bls_data, Exception):
        logger.error(f"[FoodPrices] BLS query failed: {bls_data}")
        result["blsCpi"] = None
    else:
        result["blsCpi"] = bls_data.model_dump(mode="json")
        if bls_data.series:
            result["sources"].append("BLS Consumer Price Index")

    if isinstance(usda_data, Exception):
        logger.error(f"[FoodPrices] USDA query failed: {usda_data}")
        result["usdaNass"] = None
    else:
        result["usdaNass"] = usda_data.model_dump(mode="json")
        if usda_data.commodities:
            result["sources"].append("USDA NASS QuickStats")

    # Merge highlights
    highlights = []
    if result.get("blsCpi") and result["blsCpi"].get("highlights"):
        highlights.extend(result["blsCpi"]["highlights"])
    if result.get("usdaNass") and result["usdaNass"].get("highlights"):
        highlights.extend(result["usdaNass"]["highlights"])
    result["highlights"] = highlights

    return result
