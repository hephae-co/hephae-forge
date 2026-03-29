"""User feedback — web-facing endpoint.

POST /api/feedback  — submit a thumbs-up or thumbs-down on any data item.
Auth is optional: guests can submit feedback (userId will be null).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])


class FeedbackPayload(BaseModel):
    sessionId: str
    businessSlug: str
    dataType: str
    itemId: str
    itemLabel: str = Field(..., max_length=120)
    rating: Literal["up", "down"]
    zipCode: str | None = None
    vertical: str | None = None
    tags: list[str] = []
    comment: str | None = Field(None, max_length=140)


@router.post("/feedback")
async def submit_feedback(payload: FeedbackPayload, request: Request):
    """Submit a feedback vote on a data item.

    Authentication is optional — extracts userId from Firebase token if present,
    otherwise stores feedback anonymously with sessionId only.
    """
    from hephae_db.firestore.user_feedback import write_feedback

    # Attempt to extract Firebase UID — non-blocking if no token
    user_id: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from firebase_admin import auth as firebase_auth
            token = auth_header.removeprefix("Bearer ").strip()
            decoded = firebase_auth.verify_id_token(token)
            user_id = decoded.get("uid")
        except Exception:
            pass  # anonymous feedback is fine

    await write_feedback(
        session_id=payload.sessionId,
        business_slug=payload.businessSlug,
        data_type=payload.dataType,
        item_id=payload.itemId,
        item_label=payload.itemLabel,
        rating=payload.rating,
        zip_code=payload.zipCode,
        vertical=payload.vertical,
        user_id=user_id,
        tags=payload.tags,
        comment=payload.comment,
    )

    return {"ok": True}
