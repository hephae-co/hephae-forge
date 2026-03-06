"""WorkflowEngine — state machine with SSE streaming support."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from backend.lib.db.workflows import load_workflow, save_workflow, recompute_progress
from backend.orchestrators.zipcode_research import research_zip_code
from backend.types import (
    WorkflowDocument, WorkflowPhase, ProgressEvent, WorkflowProgress,
    BusinessPhase,
)
from backend.workflow.phases.analysis import run_analysis_phase
from backend.workflow.phases.discovery import (
    run_discovery_phase, run_multi_zip_discovery_phase, to_business_workflow_states,
)
from backend.workflow.phases.evaluation import run_evaluation_phase
from backend.workflow.phases.outreach import run_outreach_phase

logger = logging.getLogger(__name__)

# In-memory registry of active workflow engines for SSE streaming
_active_engines: dict[str, "WorkflowEngine"] = {}


def get_active_engine(workflow_id: str) -> WorkflowEngine | None:
    return _active_engines.get(workflow_id)


class WorkflowEngine:
    def __init__(
        self,
        workflow: WorkflowDocument,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ):
        self.workflow = workflow
        self._on_progress = on_progress or (lambda _: None)
        self._listeners: set[Callable[[ProgressEvent], None]] = set()

    def add_listener(self, listener: Callable[[ProgressEvent], None]):
        self._listeners.add(listener)

    def remove_listener(self, listener: Callable[[ProgressEvent], None]):
        self._listeners.discard(listener)

    def _emit(self, event_type: str, message: str, business_slug: str | None = None):
        recompute_progress(self.workflow)
        event = ProgressEvent(
            type=event_type,
            workflowId=self.workflow.id,
            phase=self.workflow.phase,
            message=message,
            businessSlug=business_slug,
            progress=WorkflowProgress(**self.workflow.progress.model_dump()),
            timestamp=datetime.utcnow().isoformat(),
        )
        self._on_progress(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    async def _checkpoint(self):
        recompute_progress(self.workflow)
        await save_workflow(self.workflow)

    async def run(self):
        _active_engines[self.workflow.id] = self

        try:
            self._emit("workflow:started", f"Workflow started for zip code {self.workflow.zipCode}")

            phases: list[WorkflowPhase] = [
                WorkflowPhase.DISCOVERY,
                WorkflowPhase.ANALYSIS,
                WorkflowPhase.EVALUATION,
                WorkflowPhase.APPROVAL,
                WorkflowPhase.OUTREACH,
            ]
            start_idx = phases.index(self.workflow.phase) if self.workflow.phase in phases else 0

            for i in range(start_idx, len(phases)):
                phase = phases[i]
                self.workflow.phase = phase
                await self._checkpoint()
                self._emit("workflow:phase_changed", f"Entering {phase.value} phase")

                if phase == WorkflowPhase.DISCOVERY:
                    await self._execute_discovery()
                elif phase == WorkflowPhase.ANALYSIS:
                    await self._execute_analysis()
                elif phase == WorkflowPhase.EVALUATION:
                    await self._execute_evaluation()
                elif phase == WorkflowPhase.APPROVAL:
                    await self._checkpoint()
                    return  # Pause for human approval
                elif phase == WorkflowPhase.OUTREACH:
                    await self._execute_outreach()

            self.workflow.phase = WorkflowPhase.COMPLETED
            await self._checkpoint()
            self._emit("workflow:completed", "Workflow completed successfully")
        except Exception as e:
            logger.error(f"[WorkflowEngine] Fatal error: {e}")
            self.workflow.phase = WorkflowPhase.FAILED
            self.workflow.lastError = str(e)
            await self._checkpoint()
            self._emit("workflow:failed", f"Workflow failed: {e}")
        finally:
            _active_engines.pop(self.workflow.id, None)

    async def resume_from_outreach(self):
        _active_engines[self.workflow.id] = self

        try:
            self.workflow.phase = WorkflowPhase.OUTREACH
            await self._checkpoint()
            self._emit("workflow:phase_changed", "Entering outreach phase")

            await self._execute_outreach()

            self.workflow.phase = WorkflowPhase.COMPLETED
            await self._checkpoint()
            self._emit("workflow:completed", "Workflow completed successfully")
        except Exception as e:
            logger.error(f"[WorkflowEngine] Outreach error: {e}")
            self.workflow.phase = WorkflowPhase.FAILED
            self.workflow.lastError = str(e)
            await self._checkpoint()
            self._emit("workflow:failed", f"Workflow failed: {e}")
        finally:
            _active_engines.pop(self.workflow.id, None)

    async def _execute_discovery(self):
        business_type = self.workflow.businessType or "Restaurants"

        if self.workflow.zipCodes and len(self.workflow.zipCodes) > 0:
            # Multi-zip county mode
            self.workflow.progress.zipCodesTotal = len(self.workflow.zipCodes)
            self.workflow.progress.zipCodesScanned = 0

            discovered = await run_multi_zip_discovery_phase(
                self.workflow.zipCodes,
                business_type,
                on_progress=lambda p: (
                    setattr(self.workflow.progress, "zipCodesScanned", p["index"]),
                    self._emit(
                        "workflow:zipcode_scanning",
                        f"Scanning zip {p['zipCode']} ({p['index'] + 1}/{p['total']})",
                    ),
                ),
            )

            self.workflow.progress.zipCodesScanned = len(self.workflow.zipCodes)
        else:
            # Single zip — run discovery + zip code research in parallel
            async def _zip_research():
                try:
                    await research_zip_code(self.workflow.zipCode)
                    self._emit("workflow:zipcode_research", f"Zip code research cached for {self.workflow.zipCode}")
                except Exception as e:
                    logger.error(f"[WorkflowEngine] Zip code research non-fatal error: {e}")

            zip_task = asyncio.create_task(_zip_research())
            discovered = await run_discovery_phase(self.workflow.zipCode, business_type)
            await zip_task  # Wait for non-fatal research

        if not discovered:
            raise ValueError("No businesses discovered for this zip code")

        self.workflow.businesses = to_business_workflow_states(discovered)
        await self._checkpoint()

        for biz in self.workflow.businesses:
            self._emit("business:discovery", f"Discovered: {biz.name}", biz.slug)

    async def _execute_analysis(self):
        await run_analysis_phase(
            self.workflow.businesses,
            {
                "onEnrichmentDone": lambda slug, success: self._emit(
                    "business:enrichment_done",
                    f"Enrichment {'completed' if success else 'skipped'} for {slug}",
                    slug,
                ),
                "onCapabilityDone": lambda slug, cap, success: self._emit(
                    "business:analysis_capability",
                    f"{cap} {'completed' if success else 'failed'} for {slug}",
                    slug,
                ),
                "onInsightsDone": lambda slug, success: self._emit(
                    "business:insights_generated",
                    f"Insights {'generated' if success else 'skipped'} for {slug}",
                    slug,
                ),
                "onBusinessDone": self._on_business_analysis_done,
            },
        )

    async def _on_business_analysis_done(self, slug: str):
        self._emit("business:analysis_done", f"Analysis complete for {slug}", slug)
        await self._checkpoint()

    async def _execute_evaluation(self):
        await run_evaluation_phase(
            self.workflow.businesses,
            {
                "onBusinessEvaluated": self._on_business_evaluated,
            },
        )

    async def _on_business_evaluated(self, slug: str, passed: bool):
        self._emit(
            "business:evaluation_done",
            f"Evaluation {'passed' if passed else 'failed'} for {slug}",
            slug,
        )
        await self._checkpoint()

    async def _execute_outreach(self):
        approved_count = sum(1 for b in self.workflow.businesses if b.phase == BusinessPhase.APPROVED)
        if approved_count == 0:
            logger.info("[WorkflowEngine] No approved businesses, skipping outreach")
            return

        await run_outreach_phase(
            self.workflow.businesses,
            {
                "onBusinessOutreachDone": self._on_outreach_done,
            },
        )

    async def _on_outreach_done(self, slug: str, success: bool):
        self._emit(
            "business:outreach_done" if success else "business:outreach_failed",
            f"Outreach {'sent' if success else 'failed'} for {slug}",
            slug,
        )
        await self._checkpoint()

    def get_workflow(self) -> WorkflowDocument:
        return self.workflow


async def start_workflow_engine(
    workflow_id: str,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> WorkflowEngine:
    """Load a workflow and start the engine in background."""
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")

    engine = WorkflowEngine(workflow, on_progress)
    asyncio.create_task(engine.run())
    return engine
