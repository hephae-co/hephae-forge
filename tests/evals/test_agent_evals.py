"""ADK Agent Evaluation Suite — pytest runner.

Each test evaluates one agent using AgentEvaluator.evaluate(), which:
  1. Discovers *.test.json files in the agent's eval directory
  2. Reads test_config.json for metric thresholds
  3. Runs the agent against each test case
  4. Asserts metric scores meet thresholds

These tests require GEMINI_API_KEY to call the Gemini API.

Run all:  pytest tests/evals/ -v -m integration
Run one:  pytest tests/evals/test_agent_evals.py::test_county_resolver -v
"""

import os
from pathlib import Path

import pytest
from google.adk.evaluation import AgentEvaluator

# Resolve the evals root directory
EVALS_DIR = Path(__file__).resolve().parent

# Skip all tests in this module if GEMINI_API_KEY is not set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set — eval tests require a real Gemini API key",
    ),
]


# ---------------------------------------------------------------------------
# Workflow agents (discovery, outreach, insights)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_county_resolver():
    """Evaluate CountyResolverAgent — county name to zip code resolution."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.county_resolver.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "county_resolver"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_zipcode_scanner():
    """Evaluate ZipcodeScannerAgent — business discovery via Google Search."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.zipcode_scanner.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "zipcode_scanner"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_insights():
    """Evaluate InsightsAgent — cross-capability business insights synthesis."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.insights.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "insights"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_communicator():
    """Evaluate CommunicatorAgent — marketing outreach content formatting."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.communicator.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "communicator"),
        num_runs=1,
    )


# ---------------------------------------------------------------------------
# Capability agents (the 5 core analysis capabilities)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seo_auditor():
    """Evaluate SeoAuditorAgent — technical SEO audit across 5 categories."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.seo_auditor.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "seo_auditor"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_traffic_forecaster():
    """Evaluate traffic forecaster context gathering — POI, weather, events intelligence."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.traffic_forecaster.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "traffic_forecaster"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_competitive_analyzer():
    """Evaluate CompetitiveAnalysisPipeline — competitor profiling + market positioning."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.competitive_analyzer.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "competitive_analyzer"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_margin_surgeon_capability():
    """Evaluate MarginSurgeryOrchestrator — full margin analysis pipeline."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.margin_surgeon_capability.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "margin_surgeon_capability"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_social_media_auditor():
    """Evaluate SocialMediaAuditPipeline — social presence research + strategy."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.social_media_auditor.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "social_media_auditor"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_discovery_pipeline():
    """Evaluate DiscoveryPipeline — 4-stage business profile discovery."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.discovery_pipeline.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "discovery_pipeline"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_blog_writer():
    """Evaluate BlogWriterPipeline — research compilation + HTML blog post generation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.blog_writer.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "blog_writer"),
        num_runs=1,
    )


# ---------------------------------------------------------------------------
# Evaluator agents (QA validators for capability outputs)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seo_evaluator():
    """Evaluate SeoEvaluatorAgent — SEO audit quality validation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.evaluators.seo.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "seo"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_traffic_evaluator():
    """Evaluate TrafficEvaluatorAgent — foot traffic forecast validation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.evaluators.traffic.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "traffic"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_competitive_evaluator():
    """Evaluate CompetitiveEvaluatorAgent — competitive analysis validation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.evaluators.competitive.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "competitive"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_margin_surgeon_evaluator():
    """Evaluate MarginSurgeonEvaluatorAgent — profitability analysis validation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.evaluators.margin_surgeon.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "evaluators" / "margin_surgeon"),
        num_runs=1,
    )


# ---------------------------------------------------------------------------
# Social content agents (marketing swarm)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_marketing_swarm():
    """Evaluate MarketingPipeline — 3-stage content pipeline (creative → platform → copy)."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.marketing_swarm.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "marketing_swarm"),
        num_runs=1,
    )


# ---------------------------------------------------------------------------
# Outreach agents (multi-channel content generation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_outreach():
    """Evaluate EmailOutreachAgent — cold outreach email generation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.email_outreach.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "email_outreach"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_contact_form():
    """Evaluate ContactFormAgent — short contact form message generation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.contact_form.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "contact_form"),
        num_runs=1,
    )


# ---------------------------------------------------------------------------
# Business intelligence agents (overview, profile builder)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_overview():
    """Evaluate BusinessOverviewSynthesizer — search + maps + pulse synthesis."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.business_overview.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "business_overview"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_profile_builder():
    """Evaluate ProfileBuilderAgent — guided multi-turn profile collection flow."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.profile_builder.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "profile_builder"),
        num_runs=1,
    )


@pytest.mark.asyncio
async def test_social_post_generator():
    """Evaluate SocialPostParallel — 5-channel parallel outreach content generation."""
    await AgentEvaluator.evaluate(
        agent_module="tests.evals.social_post_generator.agent",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "social_post_generator"),
        num_runs=1,
    )
