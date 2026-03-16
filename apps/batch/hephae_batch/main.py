"""hephae-batch CLI — Cloud Run Job entry point.

Commands:
  python -m hephae_batch.main dispatcher     — check queue, run next workflow
  python -m hephae_batch.main workflow <id>   — run specific workflow by ID
  python -m hephae_batch.main area-research <area_id> <area> <business_type> <max_zips>
                                               — run area research pipeline
  python -m hephae_batch.main monitor         — run workflow monitor digest
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("hephae_batch")


async def cmd_dispatcher():
    """Check Firestore for next queued workflow and run it."""
    from hephae_db.firestore.workflows import list_workflows, save_workflow
    from hephae_api.types import WorkflowDocument, WorkflowPhase
    from hephae_api.workflows.engine import WorkflowEngine

    all_workflows = await list_workflows(limit=50, model_class=WorkflowDocument)

    active_phases = {"discovery", "qualification", "analysis", "evaluation", "outreach"}
    active = [w for w in all_workflows if w.phase.value in active_phases]
    if active:
        logger.info(f"[Dispatcher] {len(active)} active workflow(s), skipping")
        return

    queued = [w for w in all_workflows if w.phase == WorkflowPhase.QUEUED]
    if not queued:
        logger.info("[Dispatcher] No queued workflows")
        return

    queued.sort(key=lambda w: w.createdAt)
    next_wf = queued[0]

    logger.info(
        f"[Dispatcher] Starting workflow: {next_wf.id} "
        f"({next_wf.businessType} in {next_wf.zipCode}), "
        f"{len(queued) - 1} remaining in queue"
    )

    next_wf.phase = WorkflowPhase.DISCOVERY
    await save_workflow(next_wf)

    engine = WorkflowEngine(next_wf)
    await engine.run()


async def cmd_workflow(workflow_id: str):
    """Run a specific workflow by ID."""
    from hephae_db.firestore.workflows import load_workflow
    from hephae_api.types import WorkflowDocument
    from hephae_api.workflows.engine import WorkflowEngine

    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        logger.error(f"Workflow {workflow_id} not found")
        sys.exit(1)

    logger.info(f"[Batch] Running workflow {workflow_id} (phase={workflow.phase.value})")
    engine = WorkflowEngine(workflow)
    await engine.run()


async def cmd_resume_outreach(workflow_id: str):
    """Resume a workflow from the outreach phase (post-approval)."""
    from hephae_db.firestore.workflows import load_workflow
    from hephae_api.types import WorkflowDocument
    from hephae_api.workflows.engine import WorkflowEngine

    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        logger.error(f"Workflow {workflow_id} not found")
        sys.exit(1)

    logger.info(f"[Batch] Resuming outreach for workflow {workflow_id}")
    engine = WorkflowEngine(workflow)
    await engine.resume_from_outreach()


async def cmd_area_research(area_id: str, area: str, business_type: str, max_zips: int):
    """Run area research pipeline."""
    from hephae_db.firestore.research import load_area_research
    from hephae_api.types import AreaResearchDocument
    from hephae_api.workflows.orchestrators.area_research import AreaResearchOrchestrator

    doc_raw = await load_area_research(area_id)
    if doc_raw:
        doc = AreaResearchDocument(**doc_raw) if isinstance(doc_raw, dict) else doc_raw
    else:
        # Create fresh document
        from hephae_db.firestore.research import create_area_research
        raw = await create_area_research(area, business_type, [])
        doc = AreaResearchDocument(**raw)
        area_id = doc.id

    logger.info(f"[Batch] Running area research {area_id}: {area} / {business_type} (max_zips={max_zips})")
    orchestrator = AreaResearchOrchestrator(doc, max_zips)
    await orchestrator.run()


def main():
    parser = argparse.ArgumentParser(description="hephae-batch — Cloud Run Job runner")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("dispatcher", help="Check queue and run next workflow")

    wf_parser = sub.add_parser("workflow", help="Run a specific workflow")
    wf_parser.add_argument("workflow_id", help="Workflow document ID")

    resume_parser = sub.add_parser("resume-outreach", help="Resume workflow outreach")
    resume_parser.add_argument("workflow_id", help="Workflow document ID")

    ar_parser = sub.add_parser("area-research", help="Run area research pipeline")
    ar_parser.add_argument("area_id", help="Area research document ID")
    ar_parser.add_argument("area", help="Area name (e.g. 'Cook County')")
    ar_parser.add_argument("business_type", help="Business type (e.g. 'restaurant')")
    ar_parser.add_argument("--max-zips", type=int, default=10, help="Max zip codes to research")

    args = parser.parse_args()

    if args.command == "dispatcher":
        asyncio.run(cmd_dispatcher())
    elif args.command == "workflow":
        asyncio.run(cmd_workflow(args.workflow_id))
    elif args.command == "resume-outreach":
        asyncio.run(cmd_resume_outreach(args.workflow_id))
    elif args.command == "area-research":
        asyncio.run(cmd_area_research(args.area_id, args.area, args.business_type, args.max_zips))


if __name__ == "__main__":
    main()
