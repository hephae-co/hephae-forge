"""Unit tests for the heartbeat runner — delta computation, email logic, cycle execution."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Tests: compute_delta
# ---------------------------------------------------------------------------

class TestComputeDelta:
    def test_first_run_is_significant(self):
        from backend.workflows.heartbeat_runner import compute_delta

        current = {"score": 72, "summary": "Initial SEO audit", "reportUrl": "https://cdn.hephae.co/reports/test"}
        delta = compute_delta("seo", prev=None, current=current)

        assert delta["significant"] is True
        assert delta["type"] == "first_run"
        assert delta["direction"] == "new"
        assert delta["newScore"] == 72
        assert delta["prevScore"] is None

    def test_score_improved_significantly(self):
        from backend.workflows.heartbeat_runner import compute_delta

        prev = {"score": 60, "summary": "Old", "reportUrl": "old-url"}
        current = {"score": 70, "summary": "Better", "reportUrl": "new-url"}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is True
        assert delta["direction"] == "improved"
        assert delta["scoreChange"] == 10

    def test_score_declined_significantly(self):
        from backend.workflows.heartbeat_runner import compute_delta

        prev = {"score": 80, "summary": "Good"}
        current = {"score": 72, "summary": "Worse"}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is True
        assert delta["direction"] == "declined"
        assert delta["scoreChange"] == -8

    def test_small_change_not_significant(self):
        from backend.workflows.heartbeat_runner import compute_delta

        prev = {"score": 80}
        current = {"score": 82}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "improved"
        assert delta["scoreChange"] == 2

    def test_stable_score(self):
        from backend.workflows.heartbeat_runner import compute_delta

        prev = {"score": 75}
        current = {"score": 75}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "stable"
        assert delta["scoreChange"] == 0

    def test_none_scores_treated_as_zero(self):
        from backend.workflows.heartbeat_runner import compute_delta

        prev = {"score": None}
        current = {"score": None}
        delta = compute_delta("seo", prev=prev, current=current)

        assert delta["significant"] is False
        assert delta["direction"] == "stable"


# ---------------------------------------------------------------------------
# Tests: run_heartbeat_cycle
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


def _mock_capability(name: str, score: int, summary: str = "Test summary"):
    """Create a mock FullCapabilityDefinition."""
    async def runner(identity, context=None):
        return {"score": score, "summary": summary}

    def adapter(result):
        return {"score": result.get("score"), "summary": result.get("summary"), "reportUrl": f"https://cdn.hephae.co/reports/{name}"}

    cap = MagicMock()
    cap.name = name
    cap.runner = runner
    cap.response_adapter = adapter
    return cap


class TestRunHeartbeatCycle:
    @pytest.mark.asyncio
    async def test_runs_capabilities_and_sends_digest(self):
        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value={"email": "test@example.com"}),
            patch("hephae_db.context.business_context.build_business_context", new_callable=AsyncMock, return_value=None),
            patch("backend.workflows.capabilities.registry.get_capability", side_effect=lambda name: _mock_capability(name, score=85)),
            patch("hephae_db.firestore.heartbeats.record_heartbeat_run", new_callable=AsyncMock) as mock_record,
            patch("backend.workflows.heartbeat_runner._send_digest_email", new_callable=AsyncMock) as mock_email,
            patch("backend.workflows.heartbeat_runner._send_ok_email", new_callable=AsyncMock),
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "completed"
        assert result["capabilities_run"] == 2
        # SEO changed from 72→85 (significant), traffic is first_run (significant)
        assert result["significant_changes"] == 2
        mock_email.assert_called_once()
        mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_ok_email_when_no_changes(self):
        # Previous snapshot matches current scores exactly
        heartbeat = {
            **SAMPLE_HEARTBEAT,
            "capabilities": ["seo"],
            "lastSnapshot": {
                "seo": {"score": 72, "summary": "Same"},
            },
            "consecutiveOks": 1,
        }

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value={"email": "test@example.com"}),
            patch("hephae_db.context.business_context.build_business_context", new_callable=AsyncMock, return_value=None),
            patch("backend.workflows.capabilities.registry.get_capability", side_effect=lambda name: _mock_capability(name, score=72)),
            patch("hephae_db.firestore.heartbeats.record_heartbeat_run", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_digest_email", new_callable=AsyncMock) as mock_digest,
            patch("backend.workflows.heartbeat_runner._send_ok_email", new_callable=AsyncMock) as mock_ok,
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            result = await run_heartbeat_cycle(heartbeat)

        assert result["significant_changes"] == 0
        mock_digest.assert_not_called()
        mock_ok.assert_called_once()

    @pytest.mark.asyncio
    async def test_suppresses_ok_email_after_3_consecutive(self):
        heartbeat = {
            **SAMPLE_HEARTBEAT,
            "capabilities": ["seo"],
            "lastSnapshot": {"seo": {"score": 72}},
            "consecutiveOks": 3,
        }

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value={"email": "test@example.com"}),
            patch("hephae_db.context.business_context.build_business_context", new_callable=AsyncMock, return_value=None),
            patch("backend.workflows.capabilities.registry.get_capability", side_effect=lambda name: _mock_capability(name, score=72)),
            patch("hephae_db.firestore.heartbeats.record_heartbeat_run", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_digest_email", new_callable=AsyncMock) as mock_digest,
            patch("backend.workflows.heartbeat_runner._send_ok_email", new_callable=AsyncMock) as mock_ok,
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            await run_heartbeat_cycle(heartbeat)

        mock_digest.assert_not_called()
        mock_ok.assert_not_called()  # Suppressed!

    @pytest.mark.asyncio
    async def test_skips_when_business_not_found(self):
        with patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=None):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "skipped"
        assert result["reason"] == "business_not_found"

    @pytest.mark.asyncio
    async def test_skips_when_no_user_email(self):
        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value=None),
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_email"

    @pytest.mark.asyncio
    async def test_handles_capability_runner_failure_gracefully(self):
        async def failing_runner(identity, context=None):
            raise RuntimeError("Gemini rate limit")

        failing_cap = MagicMock()
        failing_cap.runner = failing_runner

        working_cap = _mock_capability("traffic", score=90)

        def get_cap(name):
            if name == "seo":
                return failing_cap
            return working_cap

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value={"email": "test@example.com"}),
            patch("hephae_db.context.business_context.build_business_context", new_callable=AsyncMock, return_value=None),
            patch("backend.workflows.capabilities.registry.get_capability", side_effect=get_cap),
            patch("hephae_db.firestore.heartbeats.record_heartbeat_run", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_digest_email", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_ok_email", new_callable=AsyncMock),
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            # Should not raise — gracefully handles failure
            result = await run_heartbeat_cycle(SAMPLE_HEARTBEAT)

        assert result["status"] == "completed"
        # SEO failed but kept previous snapshot, traffic ran successfully
        # Both are in new_snapshot (SEO from prev, traffic from fresh run)
        assert result["capabilities_run"] == 2

    @pytest.mark.asyncio
    async def test_capability_name_mapping(self):
        """Verify that 'margin' maps to 'margin_surgeon' in the registry."""
        heartbeat = {**SAMPLE_HEARTBEAT, "capabilities": ["margin"]}

        captured_names = []

        def capture_get_cap(name):
            captured_names.append(name)
            return _mock_capability(name, score=80)

        with (
            patch("hephae_db.firestore.businesses.get_business", new_callable=AsyncMock, return_value=SAMPLE_BUSINESS),
            patch("hephae_db.firestore.users.get_user", return_value={"email": "test@example.com"}),
            patch("hephae_db.context.business_context.build_business_context", new_callable=AsyncMock, return_value=None),
            patch("backend.workflows.capabilities.registry.get_capability", side_effect=capture_get_cap),
            patch("hephae_db.firestore.heartbeats.record_heartbeat_run", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_digest_email", new_callable=AsyncMock),
            patch("backend.workflows.heartbeat_runner._send_ok_email", new_callable=AsyncMock),
        ):
            from backend.workflows.heartbeat_runner import run_heartbeat_cycle

            await run_heartbeat_cycle(heartbeat)

        assert "margin_surgeon" in captured_names


# ---------------------------------------------------------------------------
# Tests: Email HTML builders
# ---------------------------------------------------------------------------

class TestEmailBuilders:
    def test_digest_html_contains_business_name(self):
        from backend.workflows.heartbeat_runner import _build_digest_html

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
        assert "80" in html  # prev score
        assert "72" in html  # new score
        assert "View Report" in html

    def test_ok_html_contains_stable_scores(self):
        from backend.workflows.heartbeat_runner import _build_ok_html

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
        from backend.workflows.heartbeat_runner import _build_digest_html

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
# Tests: Cron endpoint
# ---------------------------------------------------------------------------

class TestHeartbeatCron:
    @pytest.mark.asyncio
    async def test_cron_processes_due_heartbeats(self):
        due = [
            {"id": "hb-1", **SAMPLE_HEARTBEAT},
            {"id": "hb-2", **SAMPLE_HEARTBEAT, "businessSlug": "bobs-burgers"},
        ]

        from backend.routers.batch.heartbeat_cron import settings as cron_settings

        with (
            patch.object(cron_settings, "CRON_SECRET", "test-secret"),
            patch(
                "hephae_db.firestore.heartbeats.get_due_heartbeats",
                new_callable=AsyncMock,
                return_value=due,
            ),
            patch(
                "backend.workflows.heartbeat_runner.run_heartbeat_cycle",
                new_callable=AsyncMock,
                return_value={"status": "completed", "capabilities_run": 2, "significant_changes": 0, "email_sent": True},
            ) as mock_run,
        ):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/heartbeat-cycle",
                    headers={"Authorization": "Bearer test-secret"},
                )

        assert res.status_code == 200
        data = res.json()
        assert data["processed"] == 2
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_cron_rejects_bad_auth(self):
        from backend.routers.batch.heartbeat_cron import settings as cron_settings

        with patch.object(cron_settings, "CRON_SECRET", "real-secret"):
            from backend.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                res = await ac.get(
                    "/api/cron/heartbeat-cycle",
                    headers={"Authorization": "Bearer wrong-secret"},
                )

        assert res.status_code == 401
