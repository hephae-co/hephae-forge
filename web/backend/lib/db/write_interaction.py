"""
writeInteraction — records outreach events and inbound responses.

Writes to:
  1. BigQuery hephae.interactions — permanent event log
  2. Firestore businesses/{slug}.crm — current CRM state update

IMPORTANT: Only 'contact_form' and 'email_replied' are reliable responded signals.
'email_opened' and 'report_link_clicked' are logged but do NOT flip crm.status.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

GENUINE_RESPONSE_EVENTS = {"contact_form", "email_replied"}


async def write_interaction(
    business_slug: str,
    event_type: str,
    zip_code: Optional[str] = None,
    contact_email: Optional[str] = None,
    subject: Optional[str] = None,
    report_url: Optional[str] = None,
    outreach_number: Optional[int] = None,
) -> None:
    """Record an interaction event to Firestore + BigQuery."""
    from backend.lib.firebase import db
    from backend.lib.bigquery import bq_insert

    occurred_at = datetime.now(timezone.utc)
    interaction_id = f"{event_type}-{business_slug}-{int(occurred_at.timestamp() * 1000)}"
    is_genuine_response = event_type in GENUINE_RESPONSE_EVENTS

    # --- 1. Firestore CRM state update ---
    # Use update() so dotted paths like crm.status are treated as nested fields.
    try:
        is_outbound = event_type in ("report_sent", "follow_up_sent")
        update_payload: dict[str, object] = {"updatedAt": occurred_at}
        has_update = False

        if is_outbound and outreach_number is not None:
            update_payload["crm.outreachCount"] = outreach_number
            update_payload["crm.status"] = "outreached"
            update_payload["crm.lastOutreachAt"] = occurred_at
            if report_url:
                update_payload["crm.lastReportShared"] = report_url
            has_update = True

        if is_genuine_response:
            update_payload["crm.status"] = "responded"
            update_payload["crm.respondedAt"] = occurred_at
            has_update = True

        if has_update:
            db.document(f"businesses/{business_slug}").update(update_payload)
    except Exception as err:
        # NOT_FOUND is fine — agent result may not be written yet
        if not (hasattr(err, "code") and callable(err.code) and err.code().value[0] == 5):
            logger.error(f"[DB] Firestore writeInteraction failed for {business_slug}: {err}")

    # --- 2. BigQuery append (all events) ---
    row = {
        "interaction_id": interaction_id,
        "occurred_at": occurred_at,
        "business_slug": business_slug,
        "zip_code": zip_code,
        "event_type": event_type,
        "outreach_number": outreach_number,
        "contact_email": contact_email,
        "subject": subject,
        "report_url": report_url,
        "responded": is_genuine_response,
    }

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _bq_insert_sync(bq_insert, "interactions", row, interaction_id),
    )


async def archive_business(business_slug: str, reason: str) -> None:
    """Archive a business in Firestore CRM."""
    from backend.lib.firebase import db

    try:
        db.document(f"businesses/{business_slug}").set(
            {
                "crm.status": "archived",
                "crm.archivedAt": datetime.now(timezone.utc),
                "crm.archiveReason": reason,
                "updatedAt": datetime.now(timezone.utc),
            },
            merge=True,
        )
    except Exception as err:
        logger.error(f"[DB] archiveBusiness failed for {business_slug}: {err}")


def _bq_insert_sync(bq_insert_fn, table: str, row: dict, interaction_id: str) -> None:
    """Synchronous wrapper for fire-and-forget BQ insert."""
    import asyncio

    try:
        asyncio.run(bq_insert_fn(table, row))
    except Exception as err:
        logger.error(f"[DB] BQ interactions write failed for {interaction_id}: {err}")
