"""Pulse-specific output schemas — critique models + extended PulseInsight fields.

Re-exports base pulse models from agent_outputs.py and adds:
- InsightCritique / CritiqueResult for the Stage 4 critique loop
- Extended PulseInsight with signalSources + playbookUsed (added to agent_outputs.py)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Re-export base models so consumers can import from one place
from hephae_db.schemas.agent_outputs import (  # noqa: F401
    PulseInsight,
    PulseQuickStats,
    WeeklyPulseOutput,
    _NullSafeModel,
)


class InsightCritique(_NullSafeModel):
    """Critique of a single insight card."""

    insight_rank: int = 1
    obviousness_score: int = 50  # 0-100, higher = more obvious (bad)
    actionability_score: int = 50  # 0-100, higher = more actionable (good)
    cross_signal_score: int = 50  # 0-100, higher = better reasoning (good)
    local_briefing_score: int = 50  # 0-100, higher = better local content
    verdict: Literal["PASS", "REWRITE", "DROP"] = "PASS"
    rewrite_instruction: str = ""


class CritiqueResult(_NullSafeModel):
    """Output from PulseCritiqueAgent — evaluation of all insights."""

    overall_pass: bool = False
    local_briefing_pass: bool = True
    insights: list[InsightCritique] = Field(default_factory=list)
    summary: str = ""
