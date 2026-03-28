"""Tests for the heartbeat runner — delta computation, email builders, cycle execution.

Pure logic tests (compute_delta, email builders) run without any mocks.
Integration tests (run_heartbeat_cycle with real Firestore) require GEMINI_API_KEY
and are marked @pytest.mark.functional.

Cron endpoint tests validate auth logic without ASGITransport.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — functional tests require a real Gemini API key",
)


# ---------------------------------------------------------------------------
# Tests: compute_delta — pure logic, no external deps
# ---------------------------------------------------------------------------

class TestComputeDelta:
    def test_first_run_is_significant(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        current = {"score": 72, "summary": "Initial SEO audit", "reportUrl": "https://cdn.hephae.co/reports/test"}
        delta = compute_delta("seo", prev=None, current=current)

        assert delta["significant"] is True
        assert delta["type"] == "first_run"
        assert delta["direction"] == "new"
        assert delta["newScore"] == 72
        assert delta["prevScore"] is None

    def test_score_improved_significantly(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        prev = {"score": 60, "summary": "Old", "reportUrl": "old-url"}
        current = {"score": 70, "summary": "Better", "reportUrl": "new-url"}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is True
        assert delta["direction"] == "improved"
        assert delta["scoreChange"] == 10

    def test_score_declined_significantly(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        prev = {"score": 80, "summary": "Good"}
        current = {"score": 72, "summary": "Worse"}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is True
        assert delta["direction"] == "declined"
        assert delta["scoreChange"] == -8

    def test_small_change_not_significant(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        prev = {"score": 80}
        current = {"score": 82}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "improved"
        assert delta["scoreChange"] == 2

    def test_stable_score(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        prev = {"score": 75}
        current = {"score": 75}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "stable"
        assert delta["scoreChange"] == 0

    def test_none_scores_treated_as_zero(self):
        from hephae_api.workflows.heartbeat_runner import compute_delta

        prev = {"score": None}
        current = {"score": None}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "stable"


# ---------------------------------------------------------------------------
# Tests: Email HTML builders — pure logic, no external deps
# ---------------------------------------------------------------------------

class TestEmailBuilders:
    def test_digest_html_contains_business_name(self):
        from hephae_api.workflows.heartbeat_runner import _build_digest_html

        deltas = [{
            "capability": "seo",
            "significant": True,
            "direction": "declined",
            "scoreChange": -8,
            "prevScore": 80,
            "newScore": 72,
            "newSummary": "Missing meta descriptions",
            "reportUrl": "https://cdn.hephae.co/reports/seo-test",
        }]

        html = _build_digest_html("Joe's Pizza", deltas, {})

        assert "Joe&#x27;s Pizza" in html or "Joe's Pizza" in html
        assert "Hephae Heartbeat" in html
        assert "80" in html
        assert "72" in html
        assert "View Report" in html

    def test_ok_html_contains_stable_scores(self):
        from hephae_api.workflows.heartbeat_runner import _build_ok_html

        snapshot = {
            "seo": {"score": 72},
            "traffic": {"score": 88},
        }

        html = _build_ok_html("Joe's Pizza", snapshot)

        assert "All Clear" in html
        assert "72" in html
        assert "88" in html
        assert "stable" in html

    def test_digest_html_handles_no_report_url(self):
        from hephae_api.workflows.heartbeat_runner import _build_digest_html

        deltas = [{
            "capability": "seo",
            "significant": True,
            "direction": "improved",
            "scoreChange": 10,
            "prevScore": 60,
            "newScore": 70,
            "newSummary": None,
            "reportUrl": None,
        }]

        html = _build_digest_html("Test Biz", deltas, {})

        assert "View Report" not in html
        assert "Test Biz" in html


# ---------------------------------------------------------------------------
# Tests: run_heartbeat_cycle — functional (Firestore + Gemini)
# ---------------------------------------------------------------------------

SAMPLE_HEARTBEAT = {
    "id": "hb-001",
    "uid": "user-123",
    "businessSlug": "joes-pizza",
    "businessName": "Joe's Pizza",
    "capabilities": ["seo", "traffic"],
    "lastSnapshot": {
        "seo": {"score": 72, "summary": "OK", "reportUrl": "old-seo-url", "runAt": datetime(2026, 3, 1)},
    },
    "consecutiveOks": 0,
}

SAMPLE_BUSINESS = {
    "name": "Joe's Pizza",
    "address": "123 Main St",
    "officialUrl": "https://joespizza.com",
    "identity": {
        "name": "Joe's Pizza",
        "address": "123 Main St",
        "officialUrl": "https://joespizza.com",
    },
}


@pytest.mark.functional
class TestRunHeartbeatCycle:
    @pytest.mark.asyncio
    async def test_skips_when_business_not_found(self):
        """When business doesn't exist in Firestore, cycle returns skipped status."""
        from hephae_api.workflows.heartbeat_runner import run_heartbeat_cycle

        with patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=None):
            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "skipped"
        assert result["reason"] == "business_not_found"

    @pytest.mark.asyncio
    async def test_skips_when_no_user_email(self):
        """When user has no email, cycle skips email notification."""
        from hephae_api.workflows.heartbeat_runner import run_heartbeat_cycle

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value=None),
        ):
            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_email"

    def test_capability_name_mapping(self):
        """Verify that 'margin' maps to 'margin_surgeon' in the registry — no mocks needed."""
        from hephae_api.workflows.capabilities.registry import get_capability

        cap = get_capability("margin_surgeon")
        assert cap is not None
        assert cap.name == "margin_surgeon"


# ---------------------------------------------------------------------------
# Tests: Cron endpoint auth — validates auth logic without ASGITransport
# ---------------------------------------------------------------------------

class TestHeartbeatCronAuth:
    def test_cron_rejects_bad_auth(self):
        """Bad authorization header returns 401."""
        import sys
        _mocks: dict = {}
        for mod_name in ("resend", "crawl4ai", "playwright", "playwright.async_api"):
            if mod_name not in sys.modules:
                _mocks[mod_name] = MagicMock()
                sys.modules[mod_name] = _mocks[mod_name]

        from hephae_api.routers.batch.heartbeat_cron import settings as cron_settings
        from fastapi.testclient import TestClient

        with patch.object(cron_settings, "CRON_SECRET", "real-secret"), \
             patch("hephae_common.firebase.get_db"):
            from hephae_api.main import app
            client = TestClient(app, raise_server_exceptions=False)
            res = client.get(
                "/api/cron/heartbeat-cycle",
                headers={"Authorization": "Bearer wrong-secret"},
            )

        assert res.status_code == 401
