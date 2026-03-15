"""WorkflowEngine — state machine with SSE streaming support."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable

from hephae_db.firestore.workflows import load_workflow, save_workflow, recompute_progress
from hephae_api.workflows.orchestrators.zipcode_research import research_zip_code
from hephae_api.types import (
    WorkflowDocument, WorkflowPhase, ProgressEvent, WorkflowProgress,
    BusinessPhase,
)
from hephae_api.workflows.phases.analysis import run_analysis_phase
from hephae_api.workflows.phases.discovery import (
    run_discovery_phase, run_multi_zip_discovery_phase, to_business_workflow_states,
)
from hephae_api.workflows.phases.qualification import run_qualification_phase
from hephae_api.workflows.phases.evaluation import run_evaluation_phase
from hephae_api.workflows.phases.outreach import run_outreach_phase
from hephae_api.workflows.orchestrators.sector_research import run_sector_research

logger = logging.getLogger(__name__)

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
        recompute_progress(self.workflow, phase_enum=BusinessPhase, progress_model=WorkflowProgress)
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
        recompute_progress(self.workflow, phase_enum=BusinessPhase, progress_model=WorkflowProgress)
        await save_workflow(self.workflow)

    async def run(self):
        _active_engines[self.workflow.id] = self

        try:
            self._emit("workflow:started", f"Workflow started for zip code {self.workflow.zipCode}")

            phases: list[WorkflowPhase] = [
                WorkflowPhase.DISCOVERY,
                WorkflowPhase.QUALIFICATION,
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
                elif phase == WorkflowPhase.QUALIFICATION:
                    await self._execute_qualification()
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

    async def _run_research_parallel(self, zip_codes: list[str], business_type: str):
        """Run zipcode, area, and sector research in parallel with scan.

        Non-fatal — research failures don't block discovery. Results are
        persisted to Firestore and read later by the qualification phase.
        """
        async def _zip_research():
            for zc in zip_codes:
                try:
                    await research_zip_code(zc)
                    self._emit("workflow:zipcode_research", f"Zip code research cached for {zc}")
                except Exception as e:
                    logger.error(f"[WorkflowEngine] Zip code research non-fatal error for {zc}: {e}")

        async def _sector_research():
            try:
                await run_sector_research(sector=business_type, zip_codes=zip_codes)
                self._emit("workflow:sector_research", f"Sector research completed for {business_type}")
            except Exception as e:
                logger.error(f"[WorkflowEngine] Sector research non-fatal error: {e}")

        async def _area_research():
            try:
                from hephae_api.workflows.orchestrators.area_research import start_area_research
                city_state = None
                try:
                    from hephae_agents.discovery.zipcode_scanner import _resolve_city_state
                    city_state = await _resolve_city_state(zip_codes[0])
                except Exception:
                    pass
                area_name = f"{city_state[0]}, {city_state[1]}" if city_state else zip_codes[0]
                result = await start_area_research(area=area_name, business_type=business_type, max_zip_codes=len(zip_codes))
                self._emit("workflow:area_research", f"Area research started for {area_name}")
                orchestrator = result.get("orchestrator")
                if orchestrator and hasattr(orchestrator, "wait"):
                    await orchestrator.wait()
            except Exception as e:
                logger.error(f"[WorkflowEngine] Area research non-fatal error: {e}")

        await asyncio.gather(_zip_research(), _sector_research(), _area_research(), return_exceptions=True)

    async def _execute_discovery(self):
        business_type = self.workflow.businessType or "Restaurants"

        if self.workflow.zipCodes and len(self.workflow.zipCodes) > 0:
            self.workflow.progress.zipCodesTotal = len(self.workflow.zipCodes)
            self.workflow.progress.zipCodesScanned = 0

            research_task = asyncio.create_task(
                self._run_research_parallel(self.workflow.zipCodes, business_type)
            )

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
            await research_task
        else:
            zip_codes = [self.workflow.zipCode]
            research_task = asyncio.create_task(
                self._run_research_parallel(zip_codes, business_type)
            )
            discovered = await run_discovery_phase(self.workflow.zipCode, business_type)
            await research_task

        if not discovered:
            raise ValueError("No businesses discovered for this zip code")

        self.workflow.businesses = to_business_workflow_states(discovered)
        await self._checkpoint()

        for biz in self.workflow.businesses:
            self._emit("business:discovery", f"Discovered: {biz.name}", biz.slug)

    async def _execute_qualification(self):
        zip_code = self.workflow.zipCode
        zip_codes = self.workflow.zipCodes or [zip_code]
        business_type = self.workflow.businessType or "Restaurants"

        results = await run_qualification_phase(
            self.workflow.businesses,
            zip_code=zip_code,
            zip_codes=zip_codes,
            business_type=business_type,
            callbacks={
                "onBusinessQualified": lambda slug, outcome, score: self._emit(
                    "business:qualified",
                    f"{slug}: {outcome} (score={score})",
                    slug,
                ),
                "onQualificationDone": lambda q, p, d: self._emit(
                    "workflow:qualification_done",
                    f"Qualification done: {q} qualified, {p} parked, {d} disqualified",
                ),
            },
        )

        self.workflow.progress.qualificationQualified = len(results["qualified"])
        self.workflow.progress.qualificationParked = len(results["parked"])
        self.workflow.progress.qualificationDisqualified = len(results["disqualified"])

        # Keep all businesses in state — parked/disqualified are visible but skipped during analysis
        qualified_slugs = {biz.slug for biz in results["qualified"]}
        for biz in self.workflow.businesses:
            if biz.slug not in qualified_slugs:
                biz.phase = BusinessPhase.ANALYSIS_DONE  # Skip analysis for non-qualified

        await self._checkpoint()

        if not qualified_slugs:
            raise ValueError("No businesses qualified for deep discovery")

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
            workflow_id=self.workflow.id,
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
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")

    engine = WorkflowEngine(workflow, on_progress)
    asyncio.create_task(engine.run())
    return engine
