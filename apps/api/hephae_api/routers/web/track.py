"""POST /api/track — Firestore query/email tracking."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/track")
async def track(request: Request):
    try:
        from hephae_common.firebase import get_db

        body = await request.json()
        doc_id = body.get("id")
        query = body.get("query")
        email = body.get("email")

        # Route 1: Initial query logging
        if not doc_id and query:
            doc_ref = get_db().collection("hub_searches").document()
            doc_ref.set({
                "query": query,
                "timestamp": SERVER_TIMESTAMP,
                "status": "pending_email",
            })
            return JSONResponse({"success": True, "id": doc_ref.id})

        # Route 2: Email update
        if doc_id and email:
            doc_ref = get_db().collection("hub_searches").document(doc_id)
            doc_ref.update({
                "email": email,
                "email_captured_at": SERVER_TIMESTAMP,
                "status": "captured",
            })
            return JSONResponse({"success": True})

        return JSONResponse({"error": "Invalid Request payload"}, status_code=400)

    except Exception as e:
        logger.error(f"[API/Track] Firestore failed: {e}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
