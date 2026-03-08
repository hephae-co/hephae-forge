"""DiscoveryJob model and target validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiscoveryTarget(BaseModel):
    """A single zip code + business type combination to process."""
    zipCode: str
    businessTypes: list[str] = Field(default_factory=list)


class JobSettings(BaseModel):
    """Runtime settings for a discovery job. All have safe defaults."""
    # Skip businesses whose discovery data is fresher than this (days)
    freshnessDiscoveryDays: int = 30
    # Skip capability analysis for businesses analyzed within this window (days)
    freshnessAnalysisDays: int = 7
    # Seconds to wait between processing businesses (rate limiting)
    rateLimitSeconds: int = 3


class DiscoveryJobConfig(BaseModel):
    """Full config for one discovery job, loaded from Firestore."""
    id: str
    name: str
    targets: list[DiscoveryTarget]
    notify_email: str = "admin@hephae.co"
    settings: JobSettings = Field(default_factory=JobSettings)

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> "DiscoveryJobConfig":
        raw_settings = data.get("settings") or {}
        targets = [
            DiscoveryTarget(**t) if isinstance(t, dict) else t
            for t in data.get("targets", [])
        ]
        return cls(
            id=data["id"],
            name=data.get("name", "Unnamed Job"),
            targets=targets,
            notify_email=data.get("notifyEmail", "admin@hephae.co"),
            settings=JobSettings(**raw_settings) if raw_settings else JobSettings(),
        )
