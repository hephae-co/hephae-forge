"""Public pulse endpoints — national industry intelligence + ultralocal zipcode coverage.

GET  /api/pulse/zipcode/{zip_code}        — check ultralocal coverage for a zip
POST /api/pulse/zipcode-interest           — submit a zip code for coverage consideration
GET  /api/pulse/industry/{industry_key}   — latest national pulse summary for an industry
"""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pulse-public"])

_ZIP_RE = re.compile(r"^\d{5}$")


# ---------------------------------------------------------------------------
# GET /api/pulse/zipcode/{zip_code}
# ---------------------------------------------------------------------------

@router.get("/pulse/zipcode/{zip_code}")
async def get_zipcode_coverage(zip_code: str):
    """Check whether a zip code has ultralocal coverage.

    Returns:
        ultralocal: bool — whether the zip is actively registered
        city/state: from the registration doc if available
        lastPulseAt: ISO timestamp of last pulse run
        latestHeadline: most recent pulse headline (if available)
        interestCount: how many others have submitted this zip
    """
    if not _ZIP_RE.match(zip_code):
        return JSONResponse({"error": "Invalid zip code"}, status_code=400)

    from hephae_common.firebase import get_db
    db = get_db()

    reg_doc, interest_count = await asyncio.gather(
        asyncio.to_thread(db.collection("registered_zipcodes").document(zip_code).get),
        _get_interest_count(zip_code),
    )

    if reg_doc.exists:
        data = reg_doc.to_dict() or {}
        status = data.get("status", "")
        ultralocal = status == "active"

        last_pulse_at = data.get("lastPulseAt")
        if last_pulse_at and hasattr(last_pulse_at, "isoformat"):
            last_pulse_at = last_pulse_at.isoformat()

        return JSONResponse({
            "ultralocal": ultralocal,
            "city": data.get("city"),
            "state": data.get("state"),
            "lastPulseAt": last_pulse_at,
            "latestHeadline": data.get("lastPulseHeadline"),
            "pulseCount": data.get("pulseCount", 0),
            "interestCount": interest_count,
        })

    return JSONResponse({
        "ultralocal": False,
        "city": None,
        "state": None,
        "lastPulseAt": None,
        "latestHeadline": None,
        "pulseCount": 0,
        "interestCount": interest_count,
    })


async def _get_interest_count(zip_code: str) -> int:
    try:
        from hephae_db.firestore.zipcode_interest import get_interest_count
        return await get_interest_count(zip_code)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# POST /api/pulse/zipcode-interest
# ---------------------------------------------------------------------------

class ZipcodeInterestRequest(BaseModel):
    zipCode: str
    businessType: str | None = None
    email: str | None = None


@router.post("/pulse/zipcode-interest")
async def submit_zipcode_interest(body: ZipcodeInterestRequest):
    """Submit a zip code of interest for future ultralocal coverage."""
    if not _ZIP_RE.match(body.zipCode):
        return JSONResponse({"error": "Invalid zip code"}, status_code=400)

    # Resolve city/state from BigQuery public data if possible
    city, state = await _resolve_geo(body.zipCode)

    from hephae_db.firestore.zipcode_interest import save_zipcode_interest
    doc_id = await save_zipcode_interest(
        zip_code=body.zipCode,
        business_type=body.businessType,
        email=body.email,
        city=city,
        state=state,
    )

    interest_count = await _get_interest_count(body.zipCode)

    return JSONResponse({
        "success": True,
        "id": doc_id,
        "zipCode": body.zipCode,
        "city": city,
        "state": state,
        "interestCount": interest_count,
        "message": f"Thanks! We've noted your interest in {city or body.zipCode}. We'll add it to our coverage roadmap.",
    })


async def _resolve_geo(zip_code: str) -> tuple[str | None, str | None]:
    """Try to resolve city/state from registered_zipcodes or BigQuery."""
    try:
        from hephae_common.firebase import get_db
        db = get_db()
        doc = await asyncio.to_thread(
            db.collection("registered_zipcodes").document(zip_code).get
        )
        if doc.exists:
            data = doc.to_dict() or {}
            return data.get("city"), data.get("state")
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# GET /api/pulse/industry/{industry_key}
# ---------------------------------------------------------------------------

@router.get("/pulse/industry/{industry_key}")
async def get_industry_pulse_summary(industry_key: str):
    """Get the latest national intelligence summary for an industry.

    Returns a chatbot-friendly summary of trend data, playbooks, and signals.
    """
    industry_key = industry_key.lower().strip()

    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse

    pulse = await get_latest_industry_pulse(industry_key)
    if not pulse:
        return JSONResponse({"found": False, "industryKey": industry_key}, status_code=404)

    # Return only chatbot-consumable fields (no raw signal blobs)
    playbooks = pulse.get("nationalPlaybooks") or []
    playbook_summaries = [
        {"name": p.get("name", ""), "category": p.get("category", ""), "play": p.get("play", "")}
        for p in playbooks[:5]
    ]

    national_impact = pulse.get("nationalImpact") or {}
    # Filter to numeric values only (the interesting ones for chat)
    numeric_impact = {
        k: v for k, v in national_impact.items()
        if isinstance(v, (int, float)) and v != 0
    }

    return JSONResponse({
        "found": True,
        "industryKey": industry_key,
        "weekOf": pulse.get("weekOf"),
        "trendSummary": pulse.get("trendSummary", ""),
        "playbooks": playbook_summaries,
        "keyMetrics": numeric_impact,
        "signalsUsed": pulse.get("signalsUsed", []),
    })
