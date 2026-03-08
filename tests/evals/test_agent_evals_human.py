"""Human-curated eval tests — runs ADK evaluations against Firestore-backed fixtures.

These tests require a live Firestore connection and human-curated test fixtures
saved via the admin BusinessBrowser UI. They are NOT run in CI.

Run with:
    pytest tests/evals/test_agent_evals_human.py -m human_curated -v

Or for a specific agent:
    pytest tests/evals/test_agent_evals_human.py::test_seo_auditor_human -v

Each test:
  1. Loads test_case fixtures for the agent from Firestore (via FirestoreEvalSetsManager)
  2. Runs AgentEvaluator.evaluate_eval_set() with rubric-based quality scoring
  3. Asserts the eval set has at least one case (otherwise skip, not fail)

Thresholds:
  - rubric_based_final_response_quality_v1: 0.6 (60% of rubrics must pass)
  - response_match_score: 0.3 (lenient — expected responses are real outputs, not ideal)
"""

from __future__ import annotations

import pytest

from google.adk.evaluation import AgentEvaluator

from hephae_db.eval.firestore_eval_sets_manager import FirestoreEvalSetsManager

_APP_NAME = "hephae-hub"

_CRITERIA = {
    "rubric_based_final_response_quality_v1": 0.6,
    "response_match_score": 0.3,
}

_MANAGER = FirestoreEvalSetsManager()


def _load_eval_set(agent_key: str):
    """Load eval set from Firestore; skip test if no fixtures exist."""
    eval_set = _MANAGER.get_eval_set(_APP_NAME, agent_key)
    if eval_set is None or not eval_set.eval_cases:
        pytest.skip(
            f"No human-curated test_case fixtures found for agent_key={agent_key}. "
            "Save at least one via the admin BusinessBrowser UI."
        )
    return eval_set


@pytest.mark.human_curated
def test_seo_auditor_human():
    """SEO auditor: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("seo_auditor")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.seo_auditor.agent",
        eval_set=eval_set,
        criteria=_CRITERIA,
        num_runs=1,
    )


@pytest.mark.human_curated
def test_traffic_forecaster_human():
    """Traffic forecaster: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("traffic_forecaster")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.traffic_forecaster.agent",
        eval_set=eval_set,
        criteria=_CRITERIA,
        num_runs=1,
    )


@pytest.mark.human_curated
def test_competitive_analyzer_human():
    """Competitive analyzer: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("competitive_analyzer")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.competitive_analyzer.agent",
        eval_set=eval_set,
        criteria=_CRITERIA,
        num_runs=1,
    )


@pytest.mark.human_curated
def test_margin_surgeon_human():
    """Margin surgeon: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("margin_surgeon")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.margin_surgeon_capability.agent",
        eval_set=eval_set,
        criteria=_CRITERIA,
        num_runs=1,
    )


@pytest.mark.human_curated
def test_social_media_auditor_human():
    """Social media auditor: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("social_media_auditor")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.social_media_auditor.agent",
        eval_set=eval_set,
        criteria=_CRITERIA,
        num_runs=1,
    )


@pytest.mark.human_curated
def test_discovery_pipeline_human():
    """Discovery pipeline: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("discovery_pipeline")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.discovery_pipeline.agent",
        eval_set=eval_set,
        criteria={
            "rubric_based_final_response_quality_v1": 0.6,
            "response_match_score": 0.2,
        },
        num_runs=1,
    )


@pytest.mark.human_curated
def test_blog_writer_human():
    """Blog writer: rubric-based quality eval against human-curated fixtures."""
    eval_set = _load_eval_set("blog_writer")
    AgentEvaluator.evaluate_eval_set(
        agent_module="tests.evals.blog_writer.agent",
        eval_set=eval_set,
        criteria={
            "rubric_based_final_response_quality_v1": 0.7,
            "response_match_score": 0.2,
        },
        num_runs=1,
    )
