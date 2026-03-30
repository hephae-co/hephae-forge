"""GET /api/case-studies — Retrieve published case studies."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from hephae_db.firestore.case_studies import get_case_studies, get_case_study_by_slug

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/case-studies")
async def list_case_studies(published_only: bool = True) -> dict[str, Any]:
    """List all published case studies.

    Query params:
      - published_only (bool): Only return published case studies (default: true)

    Returns:
      {
        "case_studies": [
          {
            "id": "meal-nj-07110-07110",
            "name": "Meal Restaurant",
            "address": "...",
            "slug": "meal-nj-07110-07110",
            "isCaseStudy": true,
            "caseStudyStatus": "published",
            "caseStudyPublishedAt": "2026-03-29T...",
            "snapshot": { ... }  // Full business snapshot
          },
          ...
        ],
        "count": 1
      }
    """
    try:
        case_studies = get_case_studies(published_only=published_only)

        # Extract summary data for list view
        summaries = []
        for study in case_studies:
            summary = {
                "id": study.get("id"),
                "slug": study.get("id"),  # Use slug as slug
                "name": study.get("name"),
                "address": study.get("address"),
                "industry": study.get("businessType"),
                "caseStudyStatus": study.get("caseStudyStatus"),
                "caseStudyPublishedAt": study.get("caseStudyPublishedAt"),
            }

            # Extract metrics from snapshot if available
            snapshot = study.get("snapshot", {})
            if snapshot:
                overview = snapshot.get("overview", {})
                bs = overview.get("businessSnapshot", {})
                seo = snapshot.get("seoReport", {})
                margin = snapshot.get("marginReport", {})

                summary["metrics"] = {
                    "rating": bs.get("rating"),
                    "reviewCount": bs.get("reviewCount"),
                    "seoScore": seo.get("overallScore"),
                    "marginScore": margin.get("overall_score"),
                }

            summaries.append(summary)

        return JSONResponse(
            {
                "case_studies": summaries,
                "count": len(summaries),
            }
        )
    except Exception as err:
        logger.error(f"[API/CaseStudies] List failed: {err}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to fetch case studies"},
            status_code=500,
        )


@router.get("/case-studies/{slug}")
async def get_case_study(slug: str) -> dict[str, Any]:
    """Get a single case study by slug.

    Returns full business data for the case study, including snapshot.
    """
    try:
        case_study = get_case_study_by_slug(slug)

        if not case_study:
            return JSONResponse(
                {"error": "Case study not found"},
                status_code=404,
            )

        return JSONResponse(case_study)
    except Exception as err:
        logger.error(f"[API/CaseStudies] Get {slug} failed: {err}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to fetch case study"},
            status_code=500,
        )
