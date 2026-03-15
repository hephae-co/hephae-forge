"""
writeDiscovery — write path for discovery agent runs.

Writes to:
  1. Firestore businesses/{slug} — creates/updates the business document
  2. BigQuery hephae.discoveries — permanent append-only record
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from hephae_db.firestore.businesses import generate_slug

logger = logging.getLogger(__name__)


def strip_blobs(profile: dict[str, Any]) -> dict[str, Any]:
    """Strip binary blobs from an EnrichedProfile dict before any database write."""
    safe = {k: v for k, v in profile.items() if k != "menuScreenshotBase64"}
    return safe


def _parse_zip_code(address: Optional[str]) -> Optional[str]:
    """Parse zip code from an address string as a best-effort fallback."""
    if not address:
        return None
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", address)
    return match.group(1) if match else None


async def write_discovery(
    profile: dict[str, Any],
    triggered_by: str = "user",
    zip_code: Optional[str] = None,
    agent_version: str = "5.0.0",
) -> None:
    """Write discovery result to Firestore + BigQuery.

    Validates the profile dict against the EnrichedProfile Pydantic model
    before writing. Invalid fields are logged and stripped; the write still
    proceeds with valid data so discovery is never lost.
    """
    from hephae_common.firebase import get_db
    from hephae_common.models import EnrichedProfile
    from hephae_db.bigquery.writer import bq_insert

    # Validate against Pydantic model — coerce and strip unknown fields
    try:
        validated = EnrichedProfile.model_validate(profile)
        profile = validated.model_dump(by_alias=True, exclude_none=False)
    except Exception as err:
        logger.warning(f"[DB] Profile validation warning for {profile.get('name')}: {err}")
        # Proceed with raw dict — better to write imperfect data than lose it

    db = get_db()
    run_at = datetime.now(timezone.utc)
    run_id = f"discovery-{int(run_at.timestamp() * 1000)}"

    resolved_zip = zip_code or _parse_zip_code(profile.get("address"))
    slug = generate_slug(profile.get("name", "unknown"))

    safe = strip_blobs(profile)

    # --- 1. Firestore upsert ---
    try:
        enriched_fields = {
            "phone": profile.get("phone"),
            "email": profile.get("email"),
            "hours": profile.get("hours"),
            "googleMapsUrl": profile.get("googleMapsUrl"),
            "socialLinks": profile.get("socialLinks", {}),
            "logoUrl": profile.get("logoUrl"),
            "favicon": profile.get("favicon"),
            "primaryColor": profile.get("primaryColor"),
            "secondaryColor": profile.get("secondaryColor"),
            "persona": profile.get("persona"),
            "menuUrl": profile.get("menuUrl"),
            "menuScreenshotUrl": profile.get("menuScreenshotUrl"),
            "menuHtmlUrl": profile.get("menuHtmlUrl"),
            "competitors": profile.get("competitors", []),
            "socialProfileMetrics": profile.get("socialProfileMetrics"),
            "news": profile.get("news"),
            "aiOverview": profile.get("aiOverview"),
            "validationReport": profile.get("validationReport"),
        }

        doc_data: dict[str, Any] = {
            "name": profile.get("name"),
            "address": profile.get("address"),
            "officialUrl": profile.get("officialUrl", ""),
            "coordinates": profile.get("coordinates"),
            "updatedAt": run_at,
            "createdAt": SERVER_TIMESTAMP,
            **enriched_fields,
            "identity": enriched_fields,
        }
        if resolved_zip:
            doc_data["zipCode"] = resolved_zip

        db.document(f"businesses/{slug}").set(doc_data, merge=True)
    except Exception as err:
        logger.error(f"[DB] Firestore writeDiscovery failed for {profile.get('name')}: {err}")

    # --- 2. BigQuery append ---
    coords = profile.get("coordinates") or {}
    row = {
        "run_id": run_id,
        "business_slug": slug,
        "business_name": profile.get("name"),
        "official_url": profile.get("officialUrl", ""),
        "address": profile.get("address"),
        "city": None,
        "state": None,
        "zip_code": resolved_zip,
        "lat": coords.get("lat"),
        "lng": coords.get("lng"),
        "agent_name": "discovery_orchestrator",
        "agent_version": agent_version,
        "run_at": run_at,
        "triggered_by": triggered_by,
        "raw_data": json.dumps(safe),
    }

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _bq_insert_sync(bq_insert, "discoveries", row, run_id),
    )


def _bq_insert_sync(bq_insert_fn, table: str, row: dict, run_id: str) -> None:
    """Synchronous wrapper for fire-and-forget BQ insert."""
    import asyncio

    try:
        asyncio.run(bq_insert_fn(table, row))
    except Exception as err:
        logger.error(f"[DB] BQ discoveries write failed for {run_id}: {err}")
