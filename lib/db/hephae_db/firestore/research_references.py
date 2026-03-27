"""Firestore CRUD for research_references collection.

Each document is a structured external reference (research report, government
study, trade article) relevant to Hephae's intelligence topics.

Doc ID: SHA-1 hash of the URL (first 16 chars) — ensures idempotency.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "research_references"


async def save_references(refs: list[dict[str, Any]]) -> int:
    """Upsert a list of reference dicts. Returns count actually written."""
    if not refs:
        return 0

    db = get_db()
    saved = 0

    # Firestore batch writes — max 499 per batch
    BATCH_SIZE = 400

    for i in range(0, len(refs), BATCH_SIZE):
        chunk = refs[i : i + BATCH_SIZE]
        batch = db.batch()
        for ref in chunk:
            doc_id = ref.get("id") or ref["url"][:40]
            doc_ref = db.collection(COLLECTION).document(doc_id)
            batch.set(doc_ref, ref, merge=True)
            saved += 1
        await asyncio.to_thread(batch.commit)

    logger.info(f"[ResearchRefs] Saved {saved} references")
    return saved


async def get_existing_url_hashes() -> set[str]:
    """Return the set of all doc IDs already stored (= URL hashes).

    Used to skip re-processing URLs we already have.
    """
    db = get_db()
    docs = await asyncio.to_thread(
        lambda: list(db.collection(COLLECTION).select([]).stream())
    )
    return {d.id for d in docs}


async def get_references_by_topic(
    topic: str,
    limit: int = 20,
    min_score: float = 0.4,
) -> list[dict[str, Any]]:
    """Return references tagged with a given topic, sorted by relevance."""
    db = get_db()
    docs = await asyncio.to_thread(
        lambda: list(
            db.collection(COLLECTION)
            .where("topics", "array_contains", topic)
            .stream()
        )
    )
    refs = [d.to_dict() for d in docs]
    refs = [r for r in refs if r.get("relevance_score", 0) >= min_score]
    refs.sort(key=lambda x: -x.get("relevance_score", 0))
    return refs[:limit]


async def get_recent_references(
    week_of: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return references harvested in a given week (or all if week_of=None)."""
    db = get_db()
    query = db.collection(COLLECTION)
    if week_of:
        query = query.where("week_of", "==", week_of)
    docs = await asyncio.to_thread(lambda: list(query.stream()))
    refs = [d.to_dict() for d in docs]
    refs.sort(key=lambda x: -x.get("relevance_score", 0))
    return refs[:limit]


async def get_references_for_blog(
    topics: list[str],
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Return the most relevant references across a set of topics.

    Designed for blog writer / outreach to cite external studies.
    Returns a deduplicated, score-sorted list.
    """
    seen: set[str] = set()
    all_refs: list[dict[str, Any]] = []

    for topic in topics:
        refs = await get_references_by_topic(topic, limit=limit * 2)
        for r in refs:
            uid = r.get("id") or r.get("url", "")
            if uid not in seen:
                seen.add(uid)
                all_refs.append(r)

    all_refs.sort(key=lambda x: -x.get("relevance_score", 0))
    return all_refs[:limit]


async def search_references(
    keywords: list[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Full-scan search across title + summary for keyword matches.

    Simple client-side filter — Firestore has no full-text search.
    Suitable for small collections (<5k docs).
    """
    db = get_db()
    docs = await asyncio.to_thread(lambda: list(db.collection(COLLECTION).stream()))
    kw_lower = [k.lower() for k in keywords]
    results = []
    for doc in docs:
        d = doc.to_dict()
        text = (d.get("title", "") + " " + d.get("summary", "")).lower()
        if any(kw in text for kw in kw_lower):
            results.append(d)
    results.sort(key=lambda x: -x.get("relevance_score", 0))
    return results[:limit]
