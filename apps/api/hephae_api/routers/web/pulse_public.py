"""Public pulse endpoints — national industry intelligence + ultralocal zipcode coverage.

GET  /api/pulse/zipcode/{zip_code}        — check ultralocal coverage for a zip
POST /api/pulse/zipcode-interest           — submit a zip code for coverage consideration
GET  /api/pulse/industry/{industry_key}   — latest national pulse summary for an industry
"""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from hephae_api.lib.auth import optional_firebase_user

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
async def submit_zipcode_interest(
    body: ZipcodeInterestRequest,
    firebase_user: dict | None = Depends(optional_firebase_user),
):
    """Submit a zip code of interest for future ultralocal coverage.

    Accepts both authenticated and unauthenticated requests, but
    captures uid + email for authenticated users.
    """
    if not _ZIP_RE.match(body.zipCode):
        return JSONResponse({"error": "Invalid zip code"}, status_code=400)

    # Resolve city/state from BigQuery public data if possible
    city, state = await _resolve_geo(body.zipCode)

    uid = firebase_user.get("uid") if firebase_user else None
    user_email = firebase_user.get("email") if firebase_user else body.email

    from hephae_db.firestore.zipcode_interest import save_zipcode_interest
    doc_id = await save_zipcode_interest(
        zip_code=body.zipCode,
        business_type=body.businessType,
        email=user_email,
        uid=uid,
        city=city,
        state=state,
    )

    interest_count = await _get_interest_count(body.zipCode)

    # Send admin notification email (best-effort, don't block response)
    import asyncio
    asyncio.create_task(_notify_admin_zipcode_interest(
        body.zipCode, city, state, body.businessType, user_email, uid, interest_count,
    ))

    return JSONResponse({
        "success": True,
        "id": doc_id,
        "zipCode": body.zipCode,
        "city": city,
        "state": state,
        "interestCount": interest_count,
    })


async def _notify_admin_zipcode_interest(
    zip_code: str,
    city: str | None,
    state: str | None,
    business_type: str | None,
    email: str | None,
    uid: str | None,
    interest_count: int,
) -> None:
    """Send admin email about new coverage interest (best-effort)."""
    try:
        from hephae_api.config import settings
        from hephae_common.email import send_email

        recipients = settings.MONITOR_NOTIFY_EMAILS or settings.ADMIN_EMAIL_ALLOWLIST
        if not recipients:
            return
        email_list = [e.strip() for e in recipients.split(",") if e.strip()]
        if not email_list:
            return

        location = f"{city}, {state}" if city and state else zip_code
        subject = f"Coverage Interest: {location} ({interest_count} requests)"

        html = f"""<div style="font-family:system-ui,sans-serif;max-width:500px">
            <h3 style="color:#d97706">New Coverage Interest</h3>
            <table style="font-size:14px;border-collapse:collapse">
                <tr><td style="padding:4px 12px 4px 0;color:#6b7280">Zip Code</td><td style="font-weight:600">{zip_code}</td></tr>
                <tr><td style="padding:4px 12px 4px 0;color:#6b7280">Location</td><td>{location}</td></tr>
                <tr><td style="padding:4px 12px 4px 0;color:#6b7280">Business Type</td><td>{business_type or 'N/A'}</td></tr>
                <tr><td style="padding:4px 12px 4px 0;color:#6b7280">User</td><td>{email or 'anonymous'} {f'(uid: {uid[:8]}...)' if uid else ''}</td></tr>
                <tr><td style="padding:4px 12px 4px 0;color:#6b7280">Total Requests</td><td style="font-weight:600">{interest_count}</td></tr>
            </table>
        </div>"""

        text = f"Coverage interest: {zip_code} ({location}), {interest_count} total requests. User: {email or 'anon'}"

        await send_email(to=email_list, subject=subject, text=text, html_content=html)
        logger.info(f"[ZipcodeInterest] Admin notified for {zip_code}")
    except Exception as e:
        logger.warning(f"[ZipcodeInterest] Admin email failed: {e}")


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
