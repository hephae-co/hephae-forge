"""Analysis phase — runs capabilities via direct runner calls (no HTTP)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

from backend.workflows.agents.insights.insights_agent import generate_insights
from hephae_db.firestore.businesses import get_business
from hephae_common.firebase import get_db
from backend.types import BusinessWorkflowState, BusinessPhase
from backend.workflows.capabilities.registry import (
    get_enabled_capabilities, FullCapabilityDefinition,
)
from backend.workflows.phases.enrichment import enrich_business_profile

logger = logging.getLogger(__name__)

BATCH_CONCURRENCY = 3

PROMOTE_KEYS = [
    "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]


async def _run_capability(
    slug: str, cap_def: FullCapabilityDefinition, identity: dict
) -> dict | None:
    """Call a capability runner directly (in-process, no HTTP)."""
    try:
        result = await cap_def.runner(identity)
        if result:
            return result
        logger.error(f"[Analysis] {cap_def.name} returned None for {slug}")
        return None
    except Exception as e:
        logger.error(f"[Analysis] {cap_def.name} error for {slug}: {e}")
        return None


async def run_single_business_analysis(slug: str) -> dict:
    """Run the full capability pipeline on a single business (standalone, no workflow)."""
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

    zip_code = biz_data.get("zipCode")
    business_type = biz_data.get("businessType") or biz_data.get("category")

    if zip_code:
        try:
            from hephae_db.firestore.research import get_area_research_for_zip_code
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
                from hephae_db.firestore.research import get_zipcode_report
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
            from hephae_db.firestore.research import get_sector_research_for_type
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

    if latest_outputs:
        try:
            await asyncio.to_thread(
                db.collection("businesses").document(slug).update,
                {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"[Analysis] Firestore persist error for {slug}: {e}")

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
    """Run analysis phase on all pending businesses."""
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
                    from hephae_db.firestore.research import get_area_research_for_zip_code
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
                        from hephae_db.firestore.research import get_zipcode_report
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
                    from hephae_db.firestore.research import get_sector_research_for_type
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
                    from hephae_integrations.fda_client import is_food_related_industry
                    if is_food_related_industry(biz.businessType):
                        from hephae_integrations.bls_client import query_bls_cpi
                        from hephae_integrations.usda_client import query_usda_prices

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

            # Step 3: Run capabilities (direct runner calls, no HTTP)
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

            if latest_outputs:
                try:
                    await asyncio.to_thread(
                        db.collection("businesses").document(biz.slug).update,
                        {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
                    )
                except Exception as e:
                    logger.error(f"[Analysis] Firestore persist error for {biz.slug}: {e}")

            # Step 4: Generate insights
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
