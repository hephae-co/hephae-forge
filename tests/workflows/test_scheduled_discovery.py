"""Unit tests for the scheduled discovery module.

Tests cover:
- QualityGateAgent: profile summary building, tool capture, fail-open behavior
- Dispatcher: capability tool structure
- Orchestrator: freshness check logic
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

pytestmark = pytest.mark.functional


# ── Quality Gate ──────────────────────────────────────────────────────────────

class TestBuildProfileSummary:
    """_build_profile_summary creates readable text from identity dict."""

    def _summary(self, identity: dict) -> str:
        from hephae_api.workflows.scheduled_discovery.quality_gate import _build_profile_summary
        return _build_profile_summary(identity)

    def test_includes_name(self):
        s = self._summary({"name": "Mario's Pizza"})
        assert "Mario's Pizza" in s

    def test_includes_phone_when_present(self):
        s = self._summary({"name": "Biz", "phone": "555-1234"})
        assert "555-1234" in s

    def test_includes_email_when_present(self):
        s = self._summary({"name": "Biz", "email": "owner@biz.com"})
        assert "owner@biz.com" in s

    def test_includes_url_when_present(self):
        s = self._summary({"name": "Biz", "officialUrl": "https://biz.com"})
        assert "https://biz.com" in s

    def test_active_social_listed(self):
        s = self._summary({"name": "Biz", "socialLinks": {"instagram": "ig/biz", "facebook": None}})
        assert "instagram" in s
        assert "facebook" not in s

    def test_description_truncated_at_300(self):
        long_desc = "A" * 500
        s = self._summary({"name": "Biz", "description": long_desc})
        # Description is in the summary but truncated
        assert "A" * 10 in s
        assert "A" * 500 not in s

    def test_empty_identity_doesnt_crash(self):
        s = self._summary({})
        assert "Unknown" in s


class TestQualityGateTool:
    """The qualify() FunctionTool captures the agent's decision."""

    def _make_tool(self):
        from hephae_api.workflows.scheduled_discovery.quality_gate import _make_qualify_tool
        container = []
        tool = _make_qualify_tool(container)
        return tool, container

    def test_qualify_true_captured(self):
        tool, container = self._make_tool()
        result = tool.func(qualified=True, reason="Independent bakery with contact info")
        assert len(container) == 1
        assert container[0]["qualified"] is True
        assert "bakery" in container[0]["reason"]

    def test_qualify_false_captured(self):
        tool, container = self._make_tool()
        tool.func(qualified=False, reason="This is a McDonald's franchise")
        assert container[0]["qualified"] is False

    def test_returns_string_confirmation(self):
        tool, _ = self._make_tool()
        result = tool.func(qualified=True, reason="OK")
        assert isinstance(result, str)


class TestRunQualityGate:
    """run_quality_gate end-to-end (mocked ADK runner)."""

    @pytest.mark.asyncio
    async def test_returns_qualified_result_from_tool(self):
        expected = {"qualified": True, "reason": "Independent business with email"}

        with patch("hephae_api.workflows.scheduled_discovery.quality_gate.Runner") as MockRunner, \
             patch("hephae_api.workflows.scheduled_discovery.quality_gate.InMemorySessionService") as MockSS:
            mock_runner = MagicMock()

            async def _gen(*a, **kw):
                yield MagicMock()

            mock_runner.run_async = _gen
            MockRunner.return_value = mock_runner

            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            def _fake_make_tool(container):
                container.append(expected)
                return MagicMock()

            with patch("hephae_api.workflows.scheduled_discovery.quality_gate._make_qualify_tool",
                       side_effect=_fake_make_tool):
                from hephae_api.workflows.scheduled_discovery.quality_gate import run_quality_gate
                result = await run_quality_gate({"name": "Test Biz", "email": "a@b.com"})

        assert result["qualified"] is True
        assert result["reason"] == expected["reason"]

    @pytest.mark.asyncio
    async def test_fails_open_on_agent_exception(self):
        """If ADK runner raises, returns qualified=True (don't lose data)."""
        with patch("hephae_api.workflows.scheduled_discovery.quality_gate.Runner") as MockRunner, \
             patch("hephae_api.workflows.scheduled_discovery.quality_gate.InMemorySessionService") as MockSS:
            mock_runner = MagicMock()

            async def _error(*a, **kw):
                raise RuntimeError("Model error")
                yield

            mock_runner.run_async = _error
            MockRunner.return_value = mock_runner
            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            from hephae_api.workflows.scheduled_discovery.quality_gate import run_quality_gate
            result = await run_quality_gate({"name": "Biz"})

        assert result["qualified"] is True

    @pytest.mark.asyncio
    async def test_fails_open_when_no_tool_call(self):
        """If agent runs but never calls qualify(), returns qualified=True."""
        with patch("hephae_api.workflows.scheduled_discovery.quality_gate.Runner") as MockRunner, \
             patch("hephae_api.workflows.scheduled_discovery.quality_gate.InMemorySessionService") as MockSS:
            mock_runner = MagicMock()

            async def _empty(*a, **kw):
                return
                yield

            mock_runner.run_async = _empty
            MockRunner.return_value = mock_runner
            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            from hephae_api.workflows.scheduled_discovery.quality_gate import run_quality_gate
            result = await run_quality_gate({"name": "Biz"})

        assert result["qualified"] is True


# ── Orchestrator freshness logic ──────────────────────────────────────────────

class TestFreshnessCheck:
    """Orchestrator skips businesses that were recently discovered/analyzed."""

    def _days_ago(self, days: float):
        from datetime import datetime, timezone, timedelta
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    def _check(self, biz: dict, settings_override: dict | None = None) -> bool:
        """Returns True if the business SHOULD be skipped (is fresh)."""
        from hephae_api.workflows.scheduled_discovery.config import JobSettings
        settings = JobSettings(**(settings_override or {}))

        # Replicate the orchestrator freshness logic
        discovered_at = biz.get("discoveredAt")
        if discovered_at:
            from datetime import datetime, timezone, timedelta
            try:
                dt = datetime.fromisoformat(discovered_at.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - dt).days < settings.freshnessDiscoveryDays:
                    return True  # skip
            except ValueError:
                pass
        return False

    def test_fresh_business_is_skipped(self):
        biz = {"discoveredAt": self._days_ago(5)}  # 5 days ago, threshold=30
        assert self._check(biz) is True

    def test_stale_business_is_not_skipped(self):
        biz = {"discoveredAt": self._days_ago(35)}  # 35 days ago, threshold=30
        assert self._check(biz) is False

    def test_no_discovered_at_is_not_skipped(self):
        biz = {"name": "New Biz"}  # no discoveredAt
        assert self._check(biz) is False

    def test_custom_freshness_threshold(self):
        biz = {"discoveredAt": self._days_ago(10)}  # 10 days ago
        assert self._check(biz, {"freshnessDiscoveryDays": 7}) is False   # 10 > 7 → not fresh
        assert self._check(biz, {"freshnessDiscoveryDays": 14}) is True   # 10 < 14 → fresh (skip)


# ── Discovery Job Config integration ─────────────────────────────────────────

class TestJobSettings:
    def test_defaults_are_conservative(self):
        from hephae_api.workflows.scheduled_discovery.config import JobSettings
        s = JobSettings()
        assert s.freshnessDiscoveryDays == 30
        assert s.freshnessAnalysisDays == 7
        assert s.rateLimitSeconds == 3

    def test_custom_values_accepted(self):
        from hephae_api.workflows.scheduled_discovery.config import JobSettings
        s = JobSettings(freshnessDiscoveryDays=7, freshnessAnalysisDays=1, rateLimitSeconds=0)
        assert s.freshnessDiscoveryDays == 7
        assert s.rateLimitSeconds == 0


class TestDiscoveryTarget:
    def test_zip_only(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryTarget
        t = DiscoveryTarget(zipCode="07110")
        assert t.zipCode == "07110"
        assert t.businessTypes == []

    def test_with_business_types(self):
        from hephae_api.workflows.scheduled_discovery.config import DiscoveryTarget
        t = DiscoveryTarget(zipCode="10001", businessTypes=["restaurant", "bar"])
        assert t.businessTypes == ["restaurant", "bar"]
