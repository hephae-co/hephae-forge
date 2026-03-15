"""Qualification phase — lightweight scoring before deep discovery.

Sits between DISCOVERY and ANALYSIS. Uses research context to dynamically
calibrate a threshold, then scores each business via metadata scan + optional
full probe. Only QUALIFIED businesses proceed to ANALYSIS.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from hephae_agents.qualification import qualify_businesses
from hephae_agents.qualification.threshold import extract_research_context
from hephae_common.models import BusinessWorkflowState, BusinessPhase

logger = logging.getLogger(__name__)


async def _load_research_context(
    zip_code: str,
    business_type: str | None = None,
) -> dict[str, Any] | None:
    """Load area, zipcode, and sector research from Firestore for threshold computation."""
    ctx: dict[str, Any] = {}

    def _get(doc, key):
        """Get a value from dict or model."""
        if isinstance(doc, dict):
            return doc.get(key)
        return getattr(doc, key, None)

    try:
        from hephae_db.firestore.research import get_area_research_for_zip_code
        area_doc = await get_area_research_for_zip_code(zip_code)
        if area_doc:
            summary = _get(area_doc, "summary")
            if summary:
                ctx["area_research"] = {
                    "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                }
    except Exception as e:
        logger.warning(f"[Qualification] Area research load failed: {e}")

    try:
        from hephae_db.firestore.research import get_zipcode_report
        zip_doc = await get_zipcode_report(zip_code)
        if zip_doc:
            report = _get(zip_doc, "report")
            if report:
                sections = _get(report, "sections") if not isinstance(report, dict) else report.get("sections")
                if sections:
                    demographics = _get(sections, "demographics") if not isinstance(sections, dict) else sections.get("demographics")
                    if demographics:
                        ctx["zipcode_research"] = {
                            "report": {
                                "sections": {
                                    "demographics": demographics.model_dump(mode="json")
                                    if hasattr(demographics, "model_dump")
                                    else demographics if isinstance(demographics, dict)
                                    else {"content": getattr(demographics, "content", ""), "key_facts": getattr(demographics, "key_facts", [])},
                                },
                            },
                        }
    except Exception as e:
        logger.warning(f"[Qualification] Zipcode research load failed: {e}")

    if business_type:
        try:
            from hephae_db.firestore.research import get_sector_research_for_type
            sector_doc = await get_sector_research_for_type(business_type)
            if sector_doc:
                summary = _get(sector_doc, "summary")
                if summary:
                    ctx["sector_research"] = {
                        "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                    }
        except Exception as e:
            logger.warning(f"[Qualification] Sector research load failed: {e}")

    return extract_research_context(
        area_research=ctx.get("area_research"),
        zipcode_research=ctx.get("zipcode_research"),
        sector_research=ctx.get("sector_research"),
    ) if ctx else None


async def run_qualification_phase(
    businesses: list[BusinessWorkflowState],
    zip_code: str,
    zip_codes: list[str] | None = None,
    business_type: str | None = None,
    callbacks: dict[str, Callable] | None = None,
) -> dict[str, list[BusinessWorkflowState]]:
    """Score and classify businesses before deep discovery."""
    callbacks = callbacks or {}
    all_zips = zip_codes or [zip_code]
    logger.info(f"[Qualification] Starting for {len(businesses)} businesses in {', '.join(all_zips)}")

    # Load research context — try all zips until we find data
    research_context = None
    for zc in all_zips:
        research_context = await _load_research_context(zc, business_type)
        if research_context:
            logger.info(f"[Qualification] Research context loaded from zip {zc}")
            break
    if not research_context:
        logger.warning("[Qualification] No research context available — using default threshold")

    biz_dicts = [
        {
            "slug": biz.slug,
            "name": biz.name or "",
            "url": biz.officialUrl or "",
            "category": biz.businessType or business_type or "",
            "address": biz.address,
        }
        for biz in businesses
    ]

    results = await qualify_businesses(
        biz_dicts, research_context=research_context, run_full_probe=True,
    )

    slug_to_biz = {biz.slug: biz for biz in businesses}
    output: dict[str, list[BusinessWorkflowState]] = {
        "qualified": [], "parked": [], "disqualified": [],
    }

    for outcome_key in ("qualified", "parked", "disqualified"):
        for entry in results.get(outcome_key, []):
            slug = entry.get("slug")
            biz = slug_to_biz.get(slug)
            if not biz:
                continue

            qualification = entry.get("qualification", {})

            if outcome_key == "qualified":
                biz.phase = BusinessPhase.PENDING
            elif outcome_key == "disqualified":
                biz.phase = BusinessPhase.ANALYSIS_DONE
                biz.lastError = f"Disqualified: {', '.join(qualification.get('reasons', []))}"
            else:
                biz.phase = BusinessPhase.ANALYSIS_DONE
                biz.lastError = f"Parked: {', '.join(qualification.get('reasons', []))}"

            output[outcome_key].append(biz)

            # Persist probe data and qualification result to Firestore
            try:
                from hephae_common.firebase import get_db
                import asyncio

                db = get_db()
                update_data: dict[str, Any] = {
                    "qualificationResult": qualification,
                    "qualificationOutcome": outcome_key.upper(),
                }

                probe_data = qualification.get("probeData", {})
                if probe_data:
                    if probe_data.get("email"):
                        update_data["email"] = probe_data["email"]
                        update_data["emailStatus"] = "found"
                    if probe_data.get("phone"):
                        update_data["phone"] = probe_data["phone"]
                    if probe_data.get("social_anchors"):
                        update_data["socialLinks"] = probe_data["social_anchors"]
                    if probe_data.get("delivery_platforms"):
                        update_data["deliveryPlatforms"] = probe_data["delivery_platforms"]

                await asyncio.to_thread(
                    db.collection("businesses").document(slug).update, update_data,
                )
            except Exception as e:
                logger.warning(f"[Qualification] Firestore persist failed for {slug}: {e}")

            if callbacks.get("onBusinessQualified"):
                try:
                    callbacks["onBusinessQualified"](slug, outcome_key.upper(), qualification.get("score", 0))
                except Exception:
                    pass

    q = len(output["qualified"])
    p = len(output["parked"])
    d = len(output["disqualified"])
    logger.info(f"[Qualification] Done: {q} qualified, {p} parked, {d} disqualified")

    if callbacks.get("onQualificationDone"):
        try:
            callbacks["onQualificationDone"](q, p, d)
        except Exception:
            pass

    return output
