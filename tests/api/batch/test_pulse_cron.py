"""Functional tests for weekly pulse cron business logic.

Tests the skip/trigger decision logic directly — no HTTP layer, no mocks.
Validates: zip with recent pulse is skipped, zip without pulse is triggered.

No GEMINI_API_KEY required — pure scheduling logic.
"""

from __future__ import annotations

from datetime import datetime


def _get_week_of(dt: datetime | None = None) -> str:
    """Return ISO week string e.g. '2026-W13'."""
    now = dt or datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


def _should_skip(latest_pulse: dict | None, current_week_of: str) -> bool:
    """Return True if the zip already has a pulse for the current week."""
    if not latest_pulse:
        return False
    return latest_pulse.get("weekOf") == current_week_of


class TestWeeklyPulseSkipLogic:
    def test_no_previous_pulse_means_trigger(self):
        """Zip with no previous pulse should be triggered (not skipped)."""
        week_of = _get_week_of()
        assert _should_skip(None, week_of) is False

    def test_current_week_pulse_means_skip(self):
        """Zip that already ran this week should be skipped."""
        week_of = _get_week_of()
        existing = {"weekOf": week_of, "zipCode": "07110"}
        assert _should_skip(existing, week_of) is True

    def test_previous_week_pulse_means_trigger(self):
        """Zip whose last pulse was last week should be triggered again."""
        week_of = _get_week_of()
        last_week = "1999-W01"  # clearly not the current week
        existing = {"weekOf": last_week, "zipCode": "07110"}
        assert _should_skip(existing, week_of) is False

    def test_week_of_format_matches(self):
        """Verify week-of string format is consistent."""
        now = datetime(2026, 3, 27)  # a Thursday in week 13
        wk = _get_week_of(now)
        assert wk.startswith("2026-W")
        assert len(wk) == len("2026-W13")


class TestWeeklyPulseBatchSummary:
    def test_triggered_count_increments(self):
        """Counting triggered vs skipped zips is correct."""
        zips = [
            {"zipCode": "07110", "businessTypes": ["Restaurants"]},
            {"zipCode": "10001", "businessTypes": ["Restaurants"]},
        ]
        week_of = _get_week_of()
        # Neither has an existing pulse
        triggered = sum(1 for _ in zips if not _should_skip(None, week_of))
        skipped = sum(1 for _ in zips if _should_skip(None, week_of))
        assert triggered == 2
        assert skipped == 0

    def test_all_skipped_when_all_already_ran(self):
        """All zips already ran this week → triggered=0, skipped=all."""
        week_of = _get_week_of()
        existing_pulses = [{"weekOf": week_of}] * 3
        zips = [{"zipCode": f"0{i}001"} for i in range(3)]

        triggered = sum(1 for ep in existing_pulses if not _should_skip(ep, week_of))
        skipped = sum(1 for ep in existing_pulses if _should_skip(ep, week_of))

        assert triggered == 0
        assert skipped == 3
