"""
Shared utility — fetch latestOutputs + socialLinks from Firestore.

Used by social post generator (enriched mode) and blog writer.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.lib.report_storage import generate_slug

logger = logging.getLogger(__name__)


def fetch_latest_outputs(business_name: str) -> dict[str, Any]:
    """Read latestOutputs and socialLinks from Firestore for a business.

    Args:
        business_name: Business name (used to derive slug).

    Returns:
        {
            "outputs": {<agent_name>: {score, summary, reportUrl, ...}, ...},
            "socialLinks": {instagram, facebook, twitter, ...},
        }
        Returns empty dicts if business not found or has no data.
    """
    if not business_name:
        return {"outputs": {}, "socialLinks": {}}

    slug = generate_slug(business_name)

    try:
        from backend.lib.db.read_business import read_business

        doc = read_business(slug)
        if not doc:
            logger.info(f"[LatestOutputs] No business found for slug={slug}")
            return {"outputs": {}, "socialLinks": {}}

        outputs = doc.get("latestOutputs", {})
        social_links = doc.get("socialLinks", {})

        logger.info(
            f"[LatestOutputs] Found {len(outputs)} agent outputs for {slug}: "
            f"{list(outputs.keys())}"
        )
        return {"outputs": outputs, "socialLinks": social_links}

    except Exception as err:
        logger.warning(f"[LatestOutputs] Failed to fetch for {slug}: {err}")
        return {"outputs": {}, "socialLinks": {}}
