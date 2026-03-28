"""Unit tests for the HephaeTestRunner — QA suite runner.

Structure and JSON-parsing tests run without Gemini.
run_all_tests() is covered by integration tests in tests/integration/.
"""

from __future__ import annotations

import pytest


class TestRunnerStructure:
    """Structural tests — verify runner exposes expected test businesses."""

    def test_has_test_businesses(self):
        from hephae_api.workflows.test_runner import HephaeTestRunner
        runner = HephaeTestRunner()
        assert len(runner.businesses) >= 1
        biz = runner.businesses[0]
        assert biz["id"].startswith("qa-test")
        assert "officialUrl" in biz
        assert "name" in biz

    def test_businesses_have_required_fields(self):
        from hephae_api.workflows.test_runner import HephaeTestRunner
        runner = HephaeTestRunner()
        for biz in runner.businesses:
            assert "id" in biz
            assert "name" in biz
            assert "officialUrl" in biz
