#!/usr/bin/env python3
"""CLI runner for all ADK agent evaluations.

Usage:
    python tests/evals/run_all.py              # Run all evals
    python tests/evals/run_all.py --agent seo  # Run a specific agent eval
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GOOGLE_GENAI_API_KEY", ""))

from google.adk.evaluation import AgentEvaluator  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent

# Agent registry: name -> (module_path, eval_dir)
AGENTS = {
    # Workflow agents
    "county_resolver": (
        "tests.evals.county_resolver.agent",
        EVALS_DIR / "county_resolver",
    ),
    "zipcode_scanner": (
        "tests.evals.zipcode_scanner.agent",
        EVALS_DIR / "zipcode_scanner",
    ),
    "insights": (
        "tests.evals.insights.agent",
        EVALS_DIR / "insights",
    ),
    "communicator": (
        "tests.evals.communicator.agent",
        EVALS_DIR / "communicator",
    ),
    # Capability agents
    "seo_auditor": (
        "tests.evals.seo_auditor.agent",
        EVALS_DIR / "seo_auditor",
    ),
    "traffic_forecaster": (
        "tests.evals.traffic_forecaster.agent",
        EVALS_DIR / "traffic_forecaster",
    ),
    "competitive_analyzer": (
        "tests.evals.competitive_analyzer.agent",
        EVALS_DIR / "competitive_analyzer",
    ),
    "margin_surgeon_capability": (
        "tests.evals.margin_surgeon_capability.agent",
        EVALS_DIR / "margin_surgeon_capability",
    ),
    "social_media_auditor": (
        "tests.evals.social_media_auditor.agent",
        EVALS_DIR / "social_media_auditor",
    ),
    "discovery_pipeline": (
        "tests.evals.discovery_pipeline.agent",
        EVALS_DIR / "discovery_pipeline",
    ),
    "blog_writer": (
        "tests.evals.blog_writer.agent",
        EVALS_DIR / "blog_writer",
    ),
    # Evaluator agents (QA validators)
    "seo_evaluator": (
        "tests.evals.evaluators.seo.agent",
        EVALS_DIR / "evaluators" / "seo",
    ),
    "traffic_evaluator": (
        "tests.evals.evaluators.traffic.agent",
        EVALS_DIR / "evaluators" / "traffic",
    ),
    "competitive_evaluator": (
        "tests.evals.evaluators.competitive.agent",
        EVALS_DIR / "evaluators" / "competitive",
    ),
    "margin_surgeon_evaluator": (
        "tests.evals.evaluators.margin_surgeon.agent",
        EVALS_DIR / "evaluators" / "margin_surgeon",
    ),
}


async def run_eval(name: str, module: str, eval_dir: Path, num_runs: int) -> bool:
    """Run a single agent evaluation. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"  Evaluating: {name}")
    print(f"{'='*60}\n")
    try:
        await AgentEvaluator.evaluate(
            agent_module=module,
            eval_dataset_file_path_or_dir=str(eval_dir),
            num_runs=num_runs,
        )
        print(f"\n  {name}: PASSED")
        return True
    except AssertionError as e:
        print(f"\n  {name}: FAILED — {e}")
        return False
    except Exception as e:
        print(f"\n  {name}: ERROR — {type(e).__name__}: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Run ADK agent evaluations")
    parser.add_argument(
        "--agent",
        choices=list(AGENTS.keys()),
        help="Run a specific agent eval (default: all)",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Number of eval runs per test case (default: 1)",
    )
    args = parser.parse_args()

    agents_to_run = {args.agent: AGENTS[args.agent]} if args.agent else AGENTS

    passed = 0
    failed = 0

    for name, (module, eval_dir) in agents_to_run.items():
        success = await run_eval(name, module, eval_dir, args.num_runs)
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'='*60}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
