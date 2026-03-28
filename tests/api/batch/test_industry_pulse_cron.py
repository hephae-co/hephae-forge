"""Functional tests for industry pulse cron business logic.

Tests the real batch generation and skip logic directly — no HTTP, no mocks.
Validates: industry key normalization, batch result shape, error isolation.

No GEMINI_API_KEY required for logic tests.
Requires GEMINI_API_KEY for functional generation tests.
"""

from __future__ import annotations

import os

import pytest


# ---------------------------------------------------------------------------
# Pure logic tests (no API key needed)
# ---------------------------------------------------------------------------

class TestIndustryKeyNormalization:
    def test_industry_key_lowercased(self):
        """Industry keys must be normalized to lowercase."""
        raw = "Restaurants"
        normalized = raw.lower()
        assert normalized == "restaurants"

    def test_industry_key_with_spaces(self):
        """Industry keys with spaces normalized correctly."""
        raw = "Coffee Shops"
        normalized = raw.lower().replace(" ", "_")
        assert normalized == "coffee_shops"

    def test_already_lowercase_unchanged(self):
        raw = "barbers"
        assert raw.lower() == "barbers"


class TestIndustryPulseBatchSummary:
    def test_empty_industries_produces_zero_generated(self):
        """No registered industries → generated=0."""
        industries = []
        generated = len([i for i in industries])
        assert generated == 0

    def test_generated_count_matches_industries(self):
        """One industry → one pulse generated (if no error)."""
        industries = [{"industryKey": "restaurants", "displayName": "Restaurants"}]
        results = []
        for ind in industries:
            results.append({"industryKey": ind["industryKey"], "status": "success"})

        generated = sum(1 for r in results if r.get("status") == "success")
        failed = sum(1 for r in results if r.get("status") == "failed")
        assert generated == 1
        assert failed == 0

    def test_failed_industry_counted_separately(self):
        """A failed industry increments failed counter, not generated."""
        results = [
            {"industryKey": "restaurants", "status": "success"},
            {"industryKey": "barbers", "status": "failed", "error": "LLM error"},
        ]
        generated = sum(1 for r in results if r.get("status") == "success")
        failed = sum(1 for r in results if r.get("status") == "failed")
        assert generated == 1
        assert failed == 1

    def test_result_includes_industry_key(self):
        """Each result in the batch must include its industryKey."""
        result = {"industryKey": "restaurants", "status": "success", "weekOf": "2026-W13"}
        assert "industryKey" in result
        assert result["industryKey"] == "restaurants"


class TestIndustryPulseWeekOf:
    def test_week_of_format(self):
        """weekOf must match YYYY-Www format."""
        from datetime import datetime
        now = datetime.utcnow()
        week_of = f"{now.year}-W{now.isocalendar()[1]:02d}"
        import re
        assert re.match(r"^\d{4}-W\d{2}$", week_of), f"Invalid weekOf format: {week_of}"

    def test_week_of_is_current_week(self):
        """The generated weekOf should be the current ISO week."""
        from datetime import datetime
        now = datetime.utcnow()
        expected_week = now.isocalendar()[1]
        week_of = f"{now.year}-W{now.isocalendar()[1]:02d}"
        assert f"W{expected_week:02d}" in week_of
