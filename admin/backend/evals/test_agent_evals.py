"""ADK Agent Evaluation Suite — pytest runner.

Each test evaluates one agent using AgentEvaluator.evaluate(), which:
  1. Discovers *.test.json files in the agent's eval directory
  2. Reads test_config.json for metric thresholds
  3. Runs the agent against each test case
  4. Asserts metric scores meet thresholds

Run all:  pytest backend/evals/ -v
Run one:  pytest backend/evals/test_agent_evals.py::test_county_resolver -v
"""

from pathlib import Path

import pytest
from google.adk.evaluation import AgentEvaluator

# Resolve the evals root directory
EVALS_DIR = Path(__file__).resolve().parent


@pytest.mark.asyncio
async def test_county_resolver():
    """Evaluate CountyResolverAgent — county name to zip code resolution."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.county_resolver.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "county_resolver"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_zipcode_scanner():
    """Evaluate ZipcodeScannerAgent — business discovery via Google Search."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.zipcode_scanner.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "zipcode_scanner"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_insights():
    """Evaluate InsightsAgent — cross-capability business insights synthesis."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.insights.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "insights"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_communicator():
    """Evaluate CommunicatorAgent — marketing outreach content formatting."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.communicator.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "communicator"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_seo_evaluator():
    """Evaluate SeoEvaluatorAgent — SEO audit quality validation."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.evaluators.seo.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "seo"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_traffic_evaluator():
    """Evaluate TrafficEvaluatorAgent — foot traffic forecast validation."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.evaluators.traffic.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "traffic"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_competitive_evaluator():
    """Evaluate CompetitiveEvaluatorAgent — competitive analysis validation."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.evaluators.competitive.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "competitive"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_margin_surgeon_evaluator():
    """Evaluate MarginSurgeonEvaluatorAgent — profitability analysis validation."""
    await AgentEvaluator.evaluate(
        agent_module="backend.evals.evaluators.margin_surgeon.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "margin_surgeon"),
        num_runs=1,
    )
