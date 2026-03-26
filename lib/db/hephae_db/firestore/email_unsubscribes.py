"""Firestore CRUD for email unsubscribes.

Stores unsubscribed emails in the `email_unsubscribes` collection.
Tokens are HMAC-SHA256(email, FORGE_API_SECRET) so they are stateless
and verifiable without a DB lookup.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_COLLECTION = "email_unsubscribes"


def generate_unsubscribe_token(email: str) -> str:
    """Generate a hex HMAC token for the given email address."""
    secret = os.environ.get("FORGE_API_SECRET", "hephae-forge-secret")
    return hmac.new(secret.encode(), email.lower().encode(), hashlib.sha256).hexdigest()


def verify_unsubscribe_token(email: str, token: str) -> bool:
    """Return True if the token is valid for this email (constant-time compare)."""
    expected = generate_unsubscribe_token(email)
    return hmac.compare_digest(expected, token)


async def save_unsubscribe(email: str) -> None:
    """Record the email as unsubscribed in Firestore."""
    from hephae_common.firebase import get_db
    db = get_db()
    doc_id = email.lower().replace("@", "_at_").replace(".", "_")
    await asyncio.to_thread(
        db.collection(_COLLECTION).document(doc_id).set,
        {
            "email": email.lower(),
            "unsubscribedAt": datetime.now(timezone.utc),
        },
        True,  # merge=True
    )
    logger.info(f"[Unsubscribe] Recorded unsubscribe for {email}")


async def is_unsubscribed(email: str) -> bool:
    """Return True if this email has previously unsubscribed."""
    from hephae_common.firebase import get_db
    db = get_db()
    doc_id = email.lower().replace("@", "_at_").replace(".", "_")
    try:
        doc = await asyncio.to_thread(
            db.collection(_COLLECTION).document(doc_id).get
        )
        return doc.exists
    except Exception as e:
        logger.warning(f"[Unsubscribe] Check failed for {email}: {e}")
        return False  # fail open — don't block sends on DB errors
