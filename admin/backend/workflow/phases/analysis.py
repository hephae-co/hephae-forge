"""Analysis phase — runs capabilities from registry against each business."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

import httpx

from backend.agents.insights.insights_agent import generate_insights
from backend.config import settings
from backend.lib.forge_auth import forge_hmac_headers
from backend.lib.db.businesses import get_business
from backend.lib.firebase import get_db
from backend.types import BusinessWorkflowState, BusinessPhase
from backend.workflow.capabilities.registry import (
    get_enabled_capabilities, build_endpoint_url, FullCapabilityDefinition,
)
from backend.workflow.phases.enrichment import enrich_business_profile

logger = logging.getLogger(__name__)

BATCH_CONCURRENCY = 3

PROMOTE_KEYS = [
    "phone", "email", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]


async def _run_capability(
    slug: str, cap_def: FullCapabilityDefinition, identity: dict
) -> dict | None:
    """Call a hephae-forge capability endpoint."""
    try:
        url = build_endpoint_url(cap_def, settings.FORGE_URL)
        payload = cap_def.build_payload(identity) if cap_def.build_payload else {"identity": identity}

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=forge_hmac_headers())

        if resp.status_code != 200:
            logger.error(f"[Analysis] {cap_def.name} failed for {slug}: HTTP {resp.status_code}")
            return None

        return resp.json()
    except Exception as e:
        logger.error(f"[Analysis] {cap_def.name} error for {slug}: {e}")
        return None


async def run_single_business_analysis(slug: str) -> dict:
    """Run the full capability pipeline on a single business (standalone, no workflow).

    Returns a dict with keys: capabilitiesCompleted, capabilitiesFailed, latestOutputs, insights.
    Requires the business to already have an identity (i.e. discoveryStatus == 'discovered').
    """
    db = get_db()
    biz_data = await get_business(slug)
    if not biz_data:
        raise ValueError(f"Business {slug} not found")

    identity: dict[str, Any] = biz_data.get("identity", {
        "name": biz_data.get("name", ""),
        "address": biz_data.get("address", ""),
        "docId": slug,
    })
    if "docId" not in identity:
        identity["docId"] = slug

    # Look up area/zip/sector research context
    zip_code = biz_data.get("zipCode")
    business_type = biz_data.get("businessType") or biz_data.get("category")

    if zip_code:
        try:
            from backend.lib.db.area_research import get_area_research_for_zip_code
            area_doc = await get_area_research_for_zip_code(zip_code)
            if area_doc and area_doc.summary:
                summary = area_doc.summary
                identity["areaResearchContext"] = {
                    "areaName": area_doc.area,
                    "businessType": area_doc.businessType,
                    "resolvedState": area_doc.resolvedState or "",
                    "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                }
        except Exception:
            pass

        if "areaResearchContext" not in identity:
            try:
                from backend.lib.db.zipcode_research import get_zipcode_report
                zip_doc = await get_zipcode_report(zip_code)
                if zip_doc and zip_doc.report:
                    report = zip_doc.report
                    sections = report.sections if hasattr(report, "sections") else None
                    if sections:
                        identity["zipCodeResearchContext"] = {
                            "zipCode": zip_code,
                            "summary": report.summary if hasattr(report, "summary") else "",
                            "events": getattr(sections.events, "content", "") if sections.events else "",
                            "weather": getattr(sections.seasonal_weather, "content", "") if sections.seasonal_weather else "",
                            "demographics": getattr(sections.demographics, "content", "") if hasattr(sections, "demographics") else "",
                        }
            except Exception:
                pass

    if business_type:
        try:
            from backend.lib.db.sector_research import get_sector_research_for_type
            sector_doc = await get_sector_research_for_type(business_type)
            if sector_doc and sector_doc.summary:
                summary = sector_doc.summary
                summary_dict = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
                identity["sectorResearchContext"] = {
                    "sector": sector_doc.sector,
                    "synthesis": summary_dict.get("synthesis", {}),
                    "industryAnalysis": summary_dict.get("industryAnalysis", {}),
                }
        except Exception:
            pass

    # Run all enabled capabilities
    enabled_capabilities = get_enabled_capabilities()
    official_url = biz_data.get("officialUrl") or identity.get("officialUrl")
    caps_to_run = [
        c for c in enabled_capabilities
        if not c.should_run or c.should_run({"officialUrl": official_url, **identity})
    ]

    latest_outputs: dict[str, Any] = {}
    completed: list[str] = []
    failed: list[str] = []

    async def _run_cap(cap_def: FullCapabilityDefinition):
        raw = await _run_capability(slug, cap_def, identity)
        if raw:
            completed.append(cap_def.name)
            latest_outputs[cap_def.firestore_output_key] = cap_def.response_adapter(raw)
        else:
            failed.append(cap_def.name)

    await asyncio.gather(*[_run_cap(c) for c in caps_to_run], return_exceptions=True)

    # Persist outputs
    if latest_outputs:
        try:
            await asyncio.to_thread(
                db.collection("businesses").document(slug).update,
                {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"[Analysis] Firestore persist error for {slug}: {e}")

    # Generate insights
    insights = None
    try:
        insights = await generate_insights(slug)
    except Exception as e:
        logger.error(f"[Analysis] Insights error for {slug}: {e}")

    return {
        "capabilitiesCompleted": completed,
        "capabilitiesFailed": failed,
        "latestOutputs": latest_outputs,
        "insights": insights,
    }


async def run_analysis_phase(
    businesses: list[BusinessWorkflowState],
    callbacks: dict[str, Callable],
) -> None:
    """Run analysis phase on all pending businesses.

    callbacks: {
        onEnrichmentDone: (slug, success) -> None,
        onCapabilityDone: (slug, capability, success) -> None,
        onInsightsDone: (slug, success) -> None,
        onBusinessDone: async (slug) -> None,
    }
    """
    pending = [b for b in businesses if b.phase in (BusinessPhase.PENDING, BusinessPhase.ENRICHING, BusinessPhase.ANALYZING)]
    enabled_capabilities = get_enabled_capabilities()

    for i in range(0, len(pending), BATCH_CONCURRENCY):
        batch = pending[i : i + BATCH_CONCURRENCY]

        async def _process_business(biz: BusinessWorkflowState):
            db = get_db()

            # Step 1: Enrichment
            biz.phase = BusinessPhase.ENRICHING
            try:
                enriched = await enrich_business_profile(biz.name, biz.address, biz.slug)
                if enriched:
                    biz.enrichedProfile = enriched
                    # Update Firestore with enriched data
                    try:
                        top_level = {k: enriched[k] for k in PROMOTE_KEYS if k in enriched}
                        await asyncio.to_thread(
                            db.collection("businesses").document(biz.slug).update,
                            {**top_level, "identity": {**enriched, "docId": biz.slug}, "updatedAt": datetime.utcnow()},
                        )
                    except Exception:
                        pass
                if callbacks.get("onEnrichmentDone"):
                    callbacks["onEnrichmentDone"](biz.slug, bool(enriched))
            except Exception as e:
                logger.error(f"[Analysis] Enrichment error for {biz.slug}: {e}")
                if callbacks.get("onEnrichmentDone"):
                    callbacks["onEnrichmentDone"](biz.slug, False)

            # Step 2: Build identity
            biz.phase = BusinessPhase.ANALYZING
            identity: dict[str, Any] = {"name": biz.name, "address": biz.address, "docId": biz.slug}
            try:
                biz_data = await get_business(biz.slug)
                if biz_data:
                    identity = biz_data.get("identity", {**biz_data, "docId": biz.slug})
            except Exception:
                pass

            # Step 2b: Look up research context
            if biz.sourceZipCode:
                try:
                    from backend.lib.db.area_research import get_area_research_for_zip_code
                    area_doc = await get_area_research_for_zip_code(biz.sourceZipCode)
                    if area_doc and area_doc.summary:
                        summary = area_doc.summary
                        identity["areaResearchContext"] = {
                            "areaName": area_doc.area,
                            "businessType": area_doc.businessType,
                            "resolvedState": area_doc.resolvedState or "",
                            "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                        }
                except Exception:
                    pass

                if "areaResearchContext" not in identity:
                    try:
                        from backend.lib.db.zipcode_research import get_zipcode_report
                        zip_doc = await get_zipcode_report(biz.sourceZipCode)
                        if zip_doc and zip_doc.report:
                            report = zip_doc.report
                            sections = report.sections if hasattr(report, "sections") else None
                            if sections:
                                identity["zipCodeResearchContext"] = {
                                    "zipCode": biz.sourceZipCode,
                                    "summary": report.summary if hasattr(report, "summary") else "",
                                    "events": getattr(sections.events, "content", "") if sections.events else "",
                                    "weather": getattr(sections.seasonal_weather, "content", "") if sections.seasonal_weather else "",
                                    "demographics": getattr(sections.demographics, "content", "") if hasattr(sections, "demographics") else "",
                                }
                    except Exception:
                        pass

            if biz.businessType:
                try:
                    from backend.lib.db.sector_research import get_sector_research_for_type
                    sector_doc = await get_sector_research_for_type(biz.businessType)
                    if sector_doc and sector_doc.summary:
                        summary = sector_doc.summary
                        summary_dict = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
                        identity["sectorResearchContext"] = {
                            "sector": sector_doc.sector,
                            "synthesis": summary_dict.get("synthesis", {}),
                            "industryAnalysis": summary_dict.get("industryAnalysis", {}),
                        }
                except Exception:
                    pass

            # Step 2c: Inject food pricing context for food-related businesses
            if biz.businessType:
                try:
                    from backend.lib.fda_client import is_food_related_industry
                    if is_food_related_industry(biz.businessType):
                        from backend.lib.bls_client import query_bls_cpi
                        from backend.lib.usda_client import query_usda_prices

                        state = ""
                        area_ctx = identity.get("areaResearchContext")
                        if isinstance(area_ctx, dict):
                            state = area_ctx.get("resolvedState", "")

                        bls, usda = await asyncio.gather(
                            query_bls_cpi(biz.businessType),
                            query_usda_prices(biz.businessType, state),
                        )

                        identity["foodPricingContext"] = {
                            "blsHighlights": bls.highlights,
                            "usdaHighlights": usda.highlights,
                            "latestMonth": bls.latestMonth,
                            "source": "BLS Consumer Price Index + USDA NASS QuickStats",
                        }
                except Exception as e:
                    logger.warning(f"[Analysis] Food pricing context error for {biz.slug}: {e}")

            # Step 3: Run capabilities
            caps_to_run = [
                c for c in enabled_capabilities
                if c.name not in biz.capabilitiesCompleted
                and (not c.should_run or c.should_run({"officialUrl": biz.officialUrl, **identity}))
            ]

            latest_outputs: dict[str, Any] = {}

            async def _run_cap(cap_def: FullCapabilityDefinition):
                raw = await _run_capability(biz.slug, cap_def, identity)
                if raw:
                    biz.capabilitiesCompleted.append(cap_def.name)
                    latest_outputs[cap_def.firestore_output_key] = cap_def.response_adapter(raw)
                else:
                    biz.capabilitiesFailed.append(cap_def.name)
                callbacks["onCapabilityDone"](biz.slug, cap_def.name, raw is not None)

            await asyncio.gather(*[_run_cap(c) for c in caps_to_run], return_exceptions=True)

            # Persist outputs to Firestore
            if latest_outputs:
                try:
                    await asyncio.to_thread(
                        db.collection("businesses").document(biz.slug).update,
                        {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
                    )
                except Exception as e:
                    logger.error(f"[Analysis] Firestore persist error for {biz.slug}: {e}")

            # Step 4: Generate insights (non-fatal)
            try:
                insights = await generate_insights(biz.slug)
                if insights:
                    biz.insights = insights
                if callbacks.get("onInsightsDone"):
                    callbacks["onInsightsDone"](biz.slug, bool(insights))
            except Exception as e:
                logger.error(f"[Analysis] Insights error for {biz.slug}: {e}")
                if callbacks.get("onInsightsDone"):
                    callbacks["onInsightsDone"](biz.slug, False)

            biz.phase = BusinessPhase.ANALYSIS_DONE
            if callbacks.get("onBusinessDone"):
                await callbacks["onBusinessDone"](biz.slug)

        await asyncio.gather(*[_process_business(b) for b in batch], return_exceptions=True)
