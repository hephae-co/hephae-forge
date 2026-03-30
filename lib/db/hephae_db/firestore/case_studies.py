"""
Case studies — Firestore access for published case studies.

Queries the 'businesses' collection for documents with isCaseStudy=true.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)


def _query_case_studies_sync(published_only: bool = True) -> list[dict[str, Any]]:
    """Query Firestore for all case studies (published business profiles).

    Returns list of business documents where isCaseStudy = true, sorted by publishedAt DESC.

    Note: Avoids composite index requirement by doing filtering in Python.
    """
    try:
        db = get_db()

        # Query only by isCaseStudy=true to avoid composite index requirement
        docs = db.collection("businesses").where("isCaseStudy", "==", True).stream()

        case_studies = []
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue

            # Filter by status in Python (avoids needing a composite index)
            if published_only and data.get("caseStudyStatus") != "published":
                continue

            data["id"] = doc.id  # slug
            case_studies.append(data)

        # Sort by published date (newest first)
        case_studies.sort(
            key=lambda x: x.get("caseStudyPublishedAt", ""),
            reverse=True
        )

        return case_studies
    except Exception as err:
        logger.warning(f"[DB] Firestore case studies query failed: {err}")
        return []


def get_case_studies(published_only: bool = True) -> list[dict[str, Any]]:
    """Get all published case studies (sync).

    Returns list of case study documents sorted by publication date (newest first).
    """
    return _query_case_studies_sync(published_only)


def _get_case_study_by_slug_sync(slug: str) -> Optional[dict[str, Any]]:
    """Get a case study by business slug.

    Returns the business document if it's marked as a published case study, None otherwise.
    """
    try:
        db = get_db()
        doc = db.document(f"businesses/{slug}").get()

        if not doc.exists:
            logger.debug(f"[DB] Case study {slug} not found")
            return None

        data = doc.to_dict()
        if not data:
            return None

        # Only return if marked as published case study
        if not data.get("isCaseStudy"):
            logger.debug(f"[DB] {slug} is not marked as case study")
            return None

        if data.get("caseStudyStatus") != "published":
            logger.debug(f"[DB] {slug} case study status is {data.get('caseStudyStatus')}, not published")
            return None

        data["id"] = slug
        return data

    except Exception as err:
        logger.warning(f"[DB] Firestore case study read failed for {slug}: {err}")
        return None


def get_case_study_by_slug(slug: str) -> Optional[dict[str, Any]]:
    """Get a case study by slug (sync)."""
    return _get_case_study_by_slug_sync(slug)


def _mark_case_study_sync(slug: str, published_at: str, status: str = "published") -> None:
    """Mark a business as a case study.

    Args:
        slug: Business slug
        published_at: ISO date string (e.g., "2026-03-29T...")
        status: "draft" or "published"
    """
    try:
        db = get_db()
        db.document(f"businesses/{slug}").set(
            {
                "isCaseStudy": True,
                "caseStudyStatus": status,
                "caseStudyPublishedAt": published_at,
            },
            merge=True,
        )
    except Exception as err:
        logger.warning(f"[DB] Firestore case study mark failed for {slug}: {err}")


async def mark_case_study(
    slug: str, published_at: str, status: str = "published"
) -> None:
    """Mark a business as a case study (async)."""
    import asyncio

    await asyncio.to_thread(_mark_case_study_sync, slug, published_at, status)
