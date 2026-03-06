import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from backend.config import AgentModels
from backend.agents.deep_research import (
    run_zipcode_research,
    EscalationChecker,
    Feedback,
    SearchQuery,
    collect_sources_callback,
    zipcode_researcher,
    research_evaluator,
    refinement_researcher,
    report_composer,
    zipcode_research_pipeline,
)


# ---------------------------------------------------------------------------
# Agent initialization tests
# ---------------------------------------------------------------------------

class TestAgentInitialization:
    def test_zipcode_researcher_config(self):
        assert zipcode_researcher.name == "zipcode_researcher"
        assert zipcode_researcher.model == AgentModels.PRIMARY_MODEL
        assert "zip code" in zipcode_researcher.instruction.lower()
        assert zipcode_researcher.output_key == "research_findings"

    def test_research_evaluator_config(self):
        assert research_evaluator.name == "research_evaluator"
        assert research_evaluator.model == AgentModels.PRIMARY_MODEL
        assert research_evaluator.output_key == "research_evaluation"
        assert research_evaluator.output_schema == Feedback

    def test_refinement_researcher_config(self):
        assert refinement_researcher.name == "refinement_researcher"
        assert refinement_researcher.model == AgentModels.PRIMARY_MODEL
        assert refinement_researcher.output_key == "research_findings"

    def test_report_composer_config(self):
        assert report_composer.name == "report_composer"
        assert report_composer.model == AgentModels.PRIMARY_MODEL
        assert report_composer.output_key == "final_report"
        assert "trending" in report_composer.instruction.lower()
        assert "trends_analysis" in report_composer.instruction

    def test_pipeline_structure(self):
        agents = zipcode_research_pipeline.sub_agents
        assert len(agents) == 4
        assert agents[0].name == "zipcode_researcher"
        assert agents[1].name == "iterative_refinement_loop"
        assert agents[2].name == "trends_research_pipeline"
        assert agents[3].name == "report_composer"

    def test_loop_agent_config(self):
        loop = zipcode_research_pipeline.sub_agents[1]
        assert loop.max_iterations == 3
        assert len(loop.sub_agents) == 3
        assert loop.sub_agents[0].name == "research_evaluator"
        assert loop.sub_agents[1].name == "escalation_checker"
        assert loop.sub_agents[2].name == "refinement_researcher"


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------

class TestPydanticModels:
    def test_feedback_pass(self):
        fb = Feedback(grade="pass", comment="Looks good")
        assert fb.grade == "pass"
        assert fb.follow_up_queries is None

    def test_feedback_fail_with_queries(self):
        fb = Feedback(
            grade="fail",
            comment="Missing demographics",
            follow_up_queries=[
                SearchQuery(query="07110 demographics", reason="No population data")
            ],
        )
        assert fb.grade == "fail"
        assert len(fb.follow_up_queries) == 1
        assert fb.follow_up_queries[0].query == "07110 demographics"

    def test_feedback_invalid_grade(self):
        with pytest.raises(Exception):
            Feedback(grade="maybe", comment="Unsure")


# ---------------------------------------------------------------------------
# EscalationChecker tests
# ---------------------------------------------------------------------------

class TestEscalationChecker:
    @pytest.mark.asyncio
    async def test_escalate_on_pass(self):
        checker = EscalationChecker(name="test_checker")
        ctx = MagicMock()
        ctx.session.state = {"research_evaluation": {"grade": "pass", "comment": "Good"}}

        events = []
        async for event in checker._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions.escalate is True

    @pytest.mark.asyncio
    async def test_no_escalate_on_fail(self):
        checker = EscalationChecker(name="test_checker")
        ctx = MagicMock()
        ctx.session.state = {"research_evaluation": {"grade": "fail", "comment": "Needs work"}}

        events = []
        async for event in checker._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions is None or not getattr(events[0].actions, "escalate", False)

    @pytest.mark.asyncio
    async def test_no_escalate_on_missing_evaluation(self):
        checker = EscalationChecker(name="test_checker")
        ctx = MagicMock()
        ctx.session.state = {}

        events = []
        async for event in checker._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions is None or not getattr(events[0].actions, "escalate", False)


# ---------------------------------------------------------------------------
# Source collection callback tests
# ---------------------------------------------------------------------------

class TestCollectSourcesCallback:
    def _make_callback_ctx(self, events):
        """Create a callback context mock with a real dict-like state via MagicMock."""
        mock_session = MagicMock()
        mock_session.events = events

        state_dict = {}
        callback_ctx = MagicMock()
        callback_ctx._invocation_context.session = mock_session
        # Use a PropertyMock so `.state` returns our real dict but is assignable
        type(callback_ctx).state = property(lambda self: state_dict, lambda self, v: state_dict.update(v) if isinstance(v, dict) else None)
        # Directly patch: the callback reads/writes callback_context.state[key]
        callback_ctx.state = state_dict
        return callback_ctx, state_dict

    def test_collects_grounding_sources(self):
        mock_chunk = MagicMock()
        mock_chunk.web.uri = "https://example.com/page1"
        mock_chunk.web.title = "Example Page"
        mock_chunk.web.domain = "example.com"

        mock_event = MagicMock()
        mock_event.grounding_metadata.grounding_chunks = [mock_chunk]

        callback_ctx, state = self._make_callback_ctx([mock_event])

        collect_sources_callback(callback_ctx)

        assert "sources" in state
        assert "url_to_short_id" in state
        sources = state["sources"]
        assert len(sources) == 1
        src = list(sources.values())[0]
        assert src["url"] == "https://example.com/page1"
        assert src["title"] == "Example Page"

    def test_skips_events_without_grounding(self):
        mock_event = MagicMock()
        mock_event.grounding_metadata = None

        callback_ctx, state = self._make_callback_ctx([mock_event])

        collect_sources_callback(callback_ctx)

        assert state.get("sources", {}) == {}

    def test_deduplicates_urls(self):
        mock_chunk = MagicMock()
        mock_chunk.web.uri = "https://example.com/same"
        mock_chunk.web.title = "Same Page"
        mock_chunk.web.domain = "example.com"

        mock_event1 = MagicMock()
        mock_event1.grounding_metadata.grounding_chunks = [mock_chunk]
        mock_event2 = MagicMock()
        mock_event2.grounding_metadata.grounding_chunks = [mock_chunk]

        callback_ctx, state = self._make_callback_ctx([mock_event1, mock_event2])

        collect_sources_callback(callback_ctx)

        sources = state["sources"]
        assert len(sources) == 1


# ---------------------------------------------------------------------------
# run_zipcode_research entry point tests
# ---------------------------------------------------------------------------

class TestRunZipcodeResearch:
    @pytest.mark.asyncio
    @patch("backend.agents.deep_research.firestore_service")
    async def test_returns_cached_result(self, mock_fs):
        cached_report = {
            "summary": "Cached report for 07110",
            "zip_code": "07110",
            "sections": {"geography": {"title": "Geo", "content": "Test", "key_facts": []}},
            "sources": [],
        }
        mock_fs.get_zipcode_research.return_value = cached_report

        result = await run_zipcode_research("07110")

        assert result == cached_report
        mock_fs.get_zipcode_research.assert_called_once_with("07110")
        mock_fs.save_zipcode_research.assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.agents.deep_research.firestore_service")
    @patch("backend.agents.deep_research.Runner")
    @patch("backend.agents.deep_research.InMemorySessionService")
    async def test_runs_pipeline_when_no_cache(self, mock_session_cls, mock_runner_cls, mock_fs):
        mock_fs.get_zipcode_research.return_value = None

        # Mock session service
        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.state = {
            "final_report": json.dumps({
                "summary": "Test summary",
                "zip_code": "07110",
                "sections": {"geography": {"title": "Geo", "content": "Data", "key_facts": ["Pop: 10k"]}},
                "source_count": 2,
            }),
            "sources": {
                "src-1": {"short_id": "src-1", "title": "Wiki", "url": "https://wiki.org", "domain": "wiki.org"}
            },
        }
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value = mock_session_service

        # Mock runner — yield no events (report comes from state)
        mock_runner = MagicMock()

        async def empty_generator(*args, **kwargs):
            return
            yield  # Make it an async generator

        mock_runner.run_async = empty_generator
        mock_runner_cls.return_value = mock_runner

        result = await run_zipcode_research("07110")

        assert result["zip_code"] == "07110"
        assert result["summary"] == "Test summary"
        assert len(result["sources"]) == 1
        mock_fs.save_zipcode_research.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.agents.deep_research.firestore_service")
    @patch("backend.agents.deep_research.Runner")
    @patch("backend.agents.deep_research.InMemorySessionService")
    async def test_fallback_when_no_structured_report(self, mock_session_cls, mock_runner_cls, mock_fs):
        mock_fs.get_zipcode_research.return_value = None

        # Mock session with no final_report in state
        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value = mock_session_service

        # Mock runner — yield one text event
        mock_runner = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Raw research text about 10001"
        mock_event = MagicMock()
        mock_event.content.parts = [mock_part]

        async def event_generator(*args, **kwargs):
            yield mock_event

        mock_runner.run_async = event_generator
        mock_runner_cls.return_value = mock_runner

        result = await run_zipcode_research("10001")

        assert result["zip_code"] == "10001"
        assert "raw_findings" in result["sections"]
        assert "Raw research text" in result["sections"]["raw_findings"]["content"]
        mock_fs.save_zipcode_research.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.agents.deep_research.firestore_service")
    @patch("backend.agents.deep_research.Runner")
    @patch("backend.agents.deep_research.InMemorySessionService")
    async def test_handles_dict_final_report(self, mock_session_cls, mock_runner_cls, mock_fs):
        mock_fs.get_zipcode_research.return_value = None

        report_dict = {
            "summary": "Dict report",
            "zip_code": "20002",
            "sections": {},
            "source_count": 0,
        }

        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.state = {"final_report": report_dict, "sources": {}}
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value = mock_session_service

        mock_runner = MagicMock()

        async def empty_gen(*args, **kwargs):
            return
            yield

        mock_runner.run_async = empty_gen
        mock_runner_cls.return_value = mock_runner

        result = await run_zipcode_research("20002")

        assert result["summary"] == "Dict report"
        assert result["zip_code"] == "20002"

    @pytest.mark.asyncio
    @patch("backend.agents.deep_research.firestore_service")
    @patch("backend.agents.deep_research.Runner")
    @patch("backend.agents.deep_research.InMemorySessionService")
    async def test_handles_malformed_json_report(self, mock_session_cls, mock_runner_cls, mock_fs):
        mock_fs.get_zipcode_research.return_value = None

        mock_session_service = MagicMock()
        mock_session = MagicMock()
        mock_session.state = {"final_report": "not valid json {{{", "sources": {}}
        mock_session_service.create_session = AsyncMock(return_value=mock_session)
        mock_session_service.get_session = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value = mock_session_service

        mock_runner = MagicMock()

        async def empty_gen(*args, **kwargs):
            return
            yield

        mock_runner.run_async = empty_gen
        mock_runner_cls.return_value = mock_runner

        result = await run_zipcode_research("30303")

        # Falls back to raw_findings wrapper
        assert result["zip_code"] == "30303"
        assert "raw_findings" in result["sections"] or "summary" in result
