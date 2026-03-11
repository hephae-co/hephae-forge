"""Unit tests for the HephaeTestRunner — QA suite runner."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def runner():
    """Create a HephaeTestRunner instance."""
    with patch("hephae_common.firebase.get_db"):
        from backend.workflows.test_runner import HephaeTestRunner
        return HephaeTestRunner()


class TestRunnerStructure:
    def test_has_test_businesses(self, runner):
        assert len(runner.businesses) >= 1
        biz = runner.businesses[0]
        assert biz["id"].startswith("qa-test")
        assert "officialUrl" in biz
        assert "name" in biz

    def test_businesses_have_required_fields(self, runner):
        for biz in runner.businesses:
            assert "id" in biz
            assert "name" in biz
            assert "officialUrl" in biz


class TestEvaluateWithAgent:
    @pytest.mark.asyncio
    async def test_parses_json_output(self, runner):
        mock_event = MagicMock()
        mock_part = MagicMock()
        mock_part.text = '{"score": 85, "isHallucinated": false, "issues": []}'
        mock_event.content = MagicMock()
        mock_event.content.parts = [mock_part]

        mock_agent = MagicMock()

        with patch("backend.workflows.test_runner.Runner") as MockRunner, \
             patch("backend.workflows.test_runner.InMemorySessionService") as MockSS:
            MockSS.return_value.create_session = AsyncMock()

            async def fake_run_async(**kwargs):
                yield mock_event

            MockRunner.return_value.run_async = fake_run_async
            result = await runner.evaluate_with_agent(mock_agent, "test prompt")

        assert result["score"] == 85
        assert result["isHallucinated"] is False

    @pytest.mark.asyncio
    async def test_handles_bad_json(self, runner):
        mock_event = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "not json at all"
        mock_event.content = MagicMock()
        mock_event.content.parts = [mock_part]

        mock_agent = MagicMock()

        with patch("backend.workflows.test_runner.Runner") as MockRunner, \
             patch("backend.workflows.test_runner.InMemorySessionService") as MockSS:
            MockSS.return_value.create_session = AsyncMock()

            async def fake_run_async(**kwargs):
                yield mock_event

            MockRunner.return_value.run_async = fake_run_async
            result = await runner.evaluate_with_agent(mock_agent, "test prompt")

        assert result["score"] == 0
        assert result["isHallucinated"] is True


class TestRunAllTests:
    @pytest.mark.asyncio
    async def test_runs_all_4_capabilities(self, runner):
        eval_result = {"score": 85, "isHallucinated": False, "issues": []}

        with patch.object(runner, "evaluate_with_agent", new_callable=AsyncMock, return_value=eval_result), \
             patch("hephae_capabilities.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value={"sections": []}), \
             patch("hephae_capabilities.traffic_forecaster.runner.run_traffic_forecast", new_callable=AsyncMock, return_value={"forecast": []}), \
             patch("hephae_capabilities.competitive_analysis.runner.run_competitive_analysis", new_callable=AsyncMock, return_value={"competitors": []}), \
             patch("hephae_capabilities.margin_analyzer.runner.run_margin_analysis", new_callable=AsyncMock, return_value={"menu_items": []}), \
             patch("hephae_db.firestore.test_runs.save_test_run", new_callable=AsyncMock):

            summary = await runner.run_all_tests()

        assert summary["totalTests"] == 4
        assert summary["passedTests"] == 4
        assert summary["failedTests"] == 0
        capabilities = {r["capability"] for r in summary["results"]}
        assert capabilities == {"seo", "traffic", "competitive", "margin"}

    @pytest.mark.asyncio
    async def test_handles_capability_failure(self, runner):
        eval_result = {"score": 85, "isHallucinated": False, "issues": []}

        with patch.object(runner, "evaluate_with_agent", new_callable=AsyncMock, return_value=eval_result), \
             patch("hephae_capabilities.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, side_effect=Exception("SEO down")), \
             patch("hephae_capabilities.traffic_forecaster.runner.run_traffic_forecast", new_callable=AsyncMock, return_value={"forecast": []}), \
             patch("hephae_capabilities.competitive_analysis.runner.run_competitive_analysis", new_callable=AsyncMock, return_value={"competitors": []}), \
             patch("hephae_capabilities.margin_analyzer.runner.run_margin_analysis", new_callable=AsyncMock, return_value={"menu_items": []}), \
             patch("hephae_db.firestore.test_runs.save_test_run", new_callable=AsyncMock):

            summary = await runner.run_all_tests()

        # SEO should still appear (with score 0) since we catch exceptions
        assert summary["totalTests"] == 4
        seo_result = next(r for r in summary["results"] if r["capability"] == "seo")
        assert seo_result["score"] == 0
        assert "SEO down" in seo_result["issues"][0]

    @pytest.mark.asyncio
    async def test_persists_to_firestore(self, runner):
        eval_result = {"score": 85, "isHallucinated": False, "issues": []}

        mock_save = AsyncMock()
        with patch.object(runner, "evaluate_with_agent", new_callable=AsyncMock, return_value=eval_result), \
             patch("hephae_capabilities.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.traffic_forecaster.runner.run_traffic_forecast", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.competitive_analysis.runner.run_competitive_analysis", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.margin_analyzer.runner.run_margin_analysis", new_callable=AsyncMock, return_value={}), \
             patch("hephae_db.firestore.test_runs.save_test_run", mock_save):

            summary = await runner.run_all_tests()

        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["runId"] == summary["runId"]

    @pytest.mark.asyncio
    async def test_summary_has_correct_shape(self, runner):
        eval_result = {"score": 50, "isHallucinated": True, "issues": ["Bad output"]}

        with patch.object(runner, "evaluate_with_agent", new_callable=AsyncMock, return_value=eval_result), \
             patch("hephae_capabilities.seo_auditor.runner.run_seo_audit", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.traffic_forecaster.runner.run_traffic_forecast", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.competitive_analysis.runner.run_competitive_analysis", new_callable=AsyncMock, return_value={}), \
             patch("hephae_capabilities.margin_analyzer.runner.run_margin_analysis", new_callable=AsyncMock, return_value={}), \
             patch("hephae_db.firestore.test_runs.save_test_run", new_callable=AsyncMock):

            summary = await runner.run_all_tests()

        assert "runId" in summary
        assert "timestamp" in summary
        assert summary["totalTests"] == 4
        assert summary["failedTests"] == 4  # all fail: score < 80 or hallucinated
        assert summary["passedTests"] == 0
        for result in summary["results"]:
            assert "capability" in result
            assert "score" in result
            assert "isHallucinated" in result
            assert "responseTimeMs" in result
