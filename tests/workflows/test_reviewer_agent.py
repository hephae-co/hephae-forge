"""Unit tests for the ReviewerAgent runner.

Tests cover:
- Prompt building: identity fields + capability scores included
- Tool capture: record_review() stores correct fields
- Score clamping: 0 → 1, 11 → 10
- Fail-open: returns None on agent exception, no crash
- Integration path: run_reviewer returns captured result
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

pytestmark = pytest.mark.functional


class TestBuildReviewerPrompt:
    """_build_reviewer_prompt includes expected sections."""

    def _prompt(self, identity=None, outputs=None):
        from hephae_agents.reviewer.runner import _build_reviewer_prompt
        return _build_reviewer_prompt(
            "test-biz",
            identity or {},
            outputs or {},
        )

    def test_includes_business_name(self):
        prompt = self._prompt(identity={"name": "Joe's Pizza"})
        assert "Joe's Pizza" in prompt

    def test_includes_email_when_present(self):
        prompt = self._prompt(identity={"name": "Biz", "email": "owner@biz.com"})
        assert "owner@biz.com" in prompt

    def test_shows_not_found_for_missing_email(self):
        prompt = self._prompt(identity={"name": "Biz"})
        assert "not found" in prompt

    def test_includes_instagram_from_social_links(self):
        prompt = self._prompt(identity={
            "name": "Biz",
            "socialLinks": {"instagram": "https://instagram.com/biz"},
        })
        assert "instagram.com/biz" in prompt

    def test_includes_seo_score_from_outputs(self):
        prompt = self._prompt(
            identity={"name": "Biz"},
            outputs={"seo_auditor": {"score": 25, "summary": "Very poor SEO"}},
        )
        assert "25" in prompt
        assert "Very poor SEO" in prompt

    def test_handles_empty_identity_and_outputs(self):
        """Should not crash on empty inputs."""
        prompt = self._prompt()
        assert "record_review" in prompt

    def test_all_capability_keys_mentioned_when_present(self):
        outputs = {
            "seo_auditor": {"score": 30, "summary": "Low"},
            "competitive_analyzer": {"score": 50, "summary": "Medium"},
            "margin_surgeon": {"score": 40, "summary": "Losses"},
            "social_media_auditor": {"score": 20, "summary": "Inactive"},
            "traffic_forecaster": {"score": 60, "summary": "Moderate"},
        }
        prompt = self._prompt(identity={"name": "Biz"}, outputs=outputs)
        for label in ["SEO Audit", "Competitive", "Margin", "Social Media", "Traffic"]:
            assert label in prompt


class TestReviewTool:
    """The FunctionTool capture logic (record_review)."""

    def _make_tool_and_container(self):
        from hephae_agents.reviewer.runner import _make_review_tool
        container = []
        tool = _make_review_tool(container)
        return tool, container

    def test_captures_review_on_call(self):
        tool, container = self._make_tool_and_container()
        # Call the underlying function directly
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            tool.func(
                outreach_score=7,
                best_channel="email",
                primary_reason="Good candidate",
                strengths=["Has email", "Low SEO score"],
                concerns=["No website"],
            )
        ) if asyncio.iscoroutinefunction(tool.func) else tool.func(
            outreach_score=7,
            best_channel="email",
            primary_reason="Good candidate",
            strengths=["Has email", "Low SEO score"],
            concerns=["No website"],
        )
        assert len(container) == 1
        assert container[0]["outreach_score"] == 7
        assert container[0]["best_channel"] == "email"
        assert container[0]["primary_reason"] == "Good candidate"
        assert container[0]["strengths"] == ["Has email", "Low SEO score"]
        assert container[0]["concerns"] == ["No website"]

    def test_clamps_score_to_minimum_1(self):
        tool, container = self._make_tool_and_container()
        fn = tool.func
        if not callable(fn):
            return
        import inspect
        if inspect.iscoroutinefunction(fn):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                fn(outreach_score=-5, best_channel="email", primary_reason="x", strengths=[], concerns=[])
            )
        else:
            fn(outreach_score=-5, best_channel="email", primary_reason="x", strengths=[], concerns=[])
        assert container[0]["outreach_score"] == 1

    def test_clamps_score_to_maximum_10(self):
        tool, container = self._make_tool_and_container()
        fn = tool.func
        import inspect
        if inspect.iscoroutinefunction(fn):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                fn(outreach_score=99, best_channel="instagram", primary_reason="y", strengths=[], concerns=[])
            )
        else:
            fn(outreach_score=99, best_channel="instagram", primary_reason="y", strengths=[], concerns=[])
        assert container[0]["outreach_score"] == 10

    def test_returns_confirmation_string(self):
        tool, _ = self._make_tool_and_container()
        fn = tool.func
        import inspect
        if inspect.iscoroutinefunction(fn):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                fn(outreach_score=5, best_channel="email", primary_reason="x", strengths=[], concerns=[])
            )
        else:
            result = fn(outreach_score=5, best_channel="email", primary_reason="x", strengths=[], concerns=[])
        assert isinstance(result, str)
        assert len(result) > 0


class TestRunReviewer:
    """run_reviewer end-to-end (mocked ADK runner)."""

    @pytest.mark.asyncio
    async def test_returns_captured_result_on_success(self):
        """When the agent calls record_review, run_reviewer returns the result."""
        expected = {
            "outreach_score": 8,
            "best_channel": "email",
            "primary_reason": "Strong candidate",
            "strengths": ["Email found", "Low SEO"],
            "concerns": [],
        }

        async def _fake_run_async(*args, **kwargs):
            # Simulate the agent having called record_review by pre-filling container
            return
            yield  # make it an async generator

        # Patch at the Runner level — simulate that the agent runs and fills the container
        with patch(
            "hephae_agents.reviewer.runner.Runner"
        ) as MockRunner, patch(
            "hephae_agents.reviewer.runner.InMemorySessionService"
        ) as MockSS:
            mock_runner_instance = MagicMock()

            async def _gen(*a, **kw):
                # Simulate agent calling record_review by injecting into any container
                yield MagicMock()

            mock_runner_instance.run_async = _gen
            MockRunner.return_value = mock_runner_instance

            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            # We need to actually inject the result — patch _make_review_tool
            def _fake_make_tool(container):
                container.append(expected)
                return MagicMock()

            with patch("hephae_agents.reviewer.runner._make_review_tool", side_effect=_fake_make_tool):
                from hephae_agents.reviewer.runner import run_reviewer
                result = await run_reviewer("biz-1", {"name": "Test"}, {})

        assert result == expected

    @pytest.mark.asyncio
    async def test_returns_none_on_agent_exception(self):
        """If the ADK runner raises, run_reviewer returns None (fail-open)."""
        with patch(
            "hephae_agents.reviewer.runner.Runner"
        ) as MockRunner, patch(
            "hephae_agents.reviewer.runner.InMemorySessionService"
        ) as MockSS:
            mock_runner_instance = MagicMock()

            async def _error_gen(*a, **kw):
                raise RuntimeError("Model unavailable")
                yield  # make it a generator

            mock_runner_instance.run_async = _error_gen
            MockRunner.return_value = mock_runner_instance
            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            from hephae_agents.reviewer.runner import run_reviewer
            result = await run_reviewer("biz-2", {"name": "Biz"}, {})

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_tool_call(self):
        """If agent never calls record_review, run_reviewer returns None."""
        with patch(
            "hephae_agents.reviewer.runner.Runner"
        ) as MockRunner, patch(
            "hephae_agents.reviewer.runner.InMemorySessionService"
        ) as MockSS:
            mock_runner_instance = MagicMock()

            async def _empty_gen(*a, **kw):
                return
                yield

            mock_runner_instance.run_async = _empty_gen
            MockRunner.return_value = mock_runner_instance
            mock_ss = MagicMock()
            mock_ss.create_session = AsyncMock()
            MockSS.return_value = mock_ss

            from hephae_agents.reviewer.runner import run_reviewer
            result = await run_reviewer("biz-3", {}, {})

        assert result is None
