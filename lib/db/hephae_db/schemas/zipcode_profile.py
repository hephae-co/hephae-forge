"""Pydantic models for Zipcode Profile Discovery.

Defines the schema for the zipcode capability registry — a per-zipcode
manifest of data sources (municipal websites, news outlets, APIs, etc.)
discovered during onboarding.
"""

from __future__ import annotations

from pydantic import BaseModel


class SourceCandidate(BaseModel):
    """Phase 1 output — a possible source for a locality."""

    category: str
    exists: bool = False
    searchEvidence: str = ""
    candidateUrl: str = ""


class SourceEntry(BaseModel):
    """Phase 2 output — a verified (or not-found) source with captured details."""

    status: str = "not_checked"  # verified | not_found | not_checked | pdf_only
    url: str = ""
    lastVerified: str = ""
    subpages: dict[str, str] = {}  # e.g. {"planning_board": "https://..."}
    # Flexible flags — different per source type
    active: bool | None = None
    hasOnlinePortal: bool | None = None
    accessType: str = ""  # api | searchable_portal | pdf_only | none
    eventsUrl: str = ""
    calendarUrl: str = ""
    note: str = ""


class ZipcodeProfile(BaseModel):
    """The zipcode capability registry — stored in Firestore zipcode_profiles collection."""

    zipCode: str
    city: str = ""
    state: str = ""
    county: str = ""
    dmaName: str = ""
    profileVersion: str = "1.0"
    discoveredAt: str = ""
    refreshAfter: str = ""  # discoveredAt + 90 days
    enumeratedSources: int = 0
    confirmedSources: int = 0
    unavailableSources: int = 0
    sources: dict[str, SourceEntry] = {}
    unavailable: list[str] = []
