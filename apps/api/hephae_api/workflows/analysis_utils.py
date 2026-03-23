"""Analysis utilities — capability runner helpers and single-business analysis."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_db.firestore.businesses import get_business
from hephae_common.firebase import get_db
from hephae_api.workflows.capabilities.registry import (
    get_enabled_capabilities,
    FullCapabilityDefinition,
)

logger = logging.getLogger(__name__)

# Fields to promote from enriched identity to top-level business document
PROMOTE_KEYS = [
    "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]

# Retry configuration for retriable errors (429, 503, 529)
_CAP_MAX_RETRIES = 3
_CAP_RETRY_BACKOFF = [10, 30, 60]  # seconds between retries


class RetriableCapabilityError(Exception):
    """Raised when a capability fails with a retriable error after exhausting retries."""
    pass


def _is_retriable_error(exc: Exception) -> bool:
    """Check if an exception is a retriable API error (429, 503, 529)."""
    msg = str(exc)
    return any(code in msg for code in ("429", "503", "529", "Resource exhausted", "RESOURCE_EXHAUSTED"))


async def _run_capability(
    slug: str, cap_def: FullCapabilityDefinition, identity: dict, **kwargs
) -> dict | None:
    """Call a capability runner with retry on 429/503/529 errors."""
    last_error = None
    for attempt in range(_CAP_MAX_RETRIES):
        try:
            result = await cap_def.runner(identity, **kwargs)
            if result:
                return result
            logger.error(f"[Analysis] {cap_def.name} returned None for {slug}")
            return None
        except Exception as e:
            last_error = e
            if _is_retriable_error(e) and attempt < _CAP_MAX_RETRIES - 1:
                wait = _CAP_RETRY_BACKOFF[min(attempt, len(_CAP_RETRY_BACKOFF) - 1)]
                logger.warning(
                    f"[Analysis] {cap_def.name} retriable error for {slug} "
                    f"(attempt {attempt + 1}/{_CAP_MAX_RETRIES}): {e}, retrying in {wait}s"
                )
                await asyncio.sleep(wait)
                continue
            if _is_retriable_error(e):
                logger.error(
                    f"[Analysis] {cap_def.name} retriable error for {slug} "
                    f"after {_CAP_MAX_RETRIES} attempts: {e}"
                )
                raise RetriableCapabilityError(f"{cap_def.name}: {e}") from e
            logger.error(f"[Analysis] {cap_def.name} error for {slug}: {e}")
            return None
    return None


async def run_single_business_analysis(slug: str) -> dict:
    """Run the full capability pipeline on a single business (standalone, no workflow)."""
    from hephae_agents.insights.insights_agent import generate_insights

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

    def _g(doc, key):
        return doc.get(key) if isinstance(doc, dict) else getattr(doc, key, None)

    if zip_code:
        try:
            from hephae_db.firestore.research import get_area_research_for_zip_code
            area_doc = await get_area_research_for_zip_code(zip_code)
            if area_doc:
                summary = _g(area_doc, "summary")
                if summary:
                    identity["areaResearchContext"] = {
                        "areaName": _g(area_doc, "area") or "",
                        "businessType": _g(area_doc, "businessType") or "",
                        "resolvedState": _g(area_doc, "resolvedState") or "",
                        "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                    }
        except Exception:
            pass

        if "areaResearchContext" not in identity:
            try:
                from hephae_db.firestore.research import get_zipcode_report
                zip_doc = await get_zipcode_report(zip_code)
                if zip_doc:
                    report = _g(zip_doc, "report")
                    if report:
                        sections = _g(report, "sections") if not isinstance(report, dict) else report.get("sections")
                        if sections:
                            _sg = lambda s, k: (s.get(k) if isinstance(s, dict) else getattr(s, k, None))
                            events = _sg(sections, "events")
                            weather = _sg(sections, "seasonal_weather")
                            demographics = _sg(sections, "demographics")
                            identity["zipCodeResearchContext"] = {
                                "zipCode": zip_code,
                                "summary": _g(report, "summary") or "",
                                "events": (_g(events, "content") or "") if events else "",
                                "weather": (_g(weather, "content") or "") if weather else "",
                                "demographics": (_g(demographics, "content") or "") if demographics else "",
                            }
            except Exception:
                pass

    if business_type:
        try:
            from hephae_db.firestore.research import get_sector_research_for_type
            sector_doc = await get_sector_research_for_type(business_type)
            if sector_doc:
                summary = _g(sector_doc, "summary")
                if summary:
                    summary_dict = (
                        summary.model_dump(mode="json")
                        if hasattr(summary, "model_dump")
                        else (summary if isinstance(summary, dict) else {})
                    )
                    identity["sectorResearchContext"] = {
                        "sector": _g(sector_doc, "sector") or "",
                        "synthesis": summary_dict.get("synthesis", {}),
                        "industryAnalysis": summary_dict.get("industryAnalysis", {}),
                    }
        except Exception:
            pass

    enabled_capabilities = get_enabled_capabilities()
    official_url = biz_data.get("officialUrl") or identity.get("officialUrl")
    should_run_ctx = {**biz_data, **identity, "officialUrl": official_url}
    caps_to_run = [
        c for c in enabled_capabilities
        if not c.should_run or c.should_run(should_run_ctx)
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
