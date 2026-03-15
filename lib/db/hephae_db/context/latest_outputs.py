"""
Fetch latestOutputs + socialLinks from Firestore.

Used by social post generator (enriched mode) and blog writer.
"""

from __future__ import annotations

import logging
from typing import Any

from hephae_db.firestore.businesses import generate_slug, read_business

logger = logging.getLogger(__name__)


def fetch_latest_outputs(business_name: str) -> dict[str, Any]:
    """Read latestOutputs and socialLinks from Firestore for a business.

    Returns:
        {
            "outputs": {<agent_name>: {score, summary, reportUrl, ...}, ...},
            "socialLinks": {instagram, facebook, twitter, ...},
        }
    """
    if not business_name:
        return {"outputs": {}, "socialLinks": {}}

    slug = generate_slug(business_name)

    try:
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
