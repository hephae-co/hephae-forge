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
    _inherit_urls_from_firestore, _find_missing_websites,
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

        Staleness policy:
        - Zipcode research: reuse if < 7 days old, refresh only volatile sections
          (weather, events, trending) if > 24 hours old
        - Sector research: reuse if < 7 days old
        - Area research: reuse if < 7 days old

        Non-fatal — research failures don't block discovery.
        """
        from hephae_db.firestore.research import (
            get_zipcode_report, get_area_research_for_zip_code,
            get_sector_research_for_type,
        )

        FULL_REFRESH_DAYS = 7
        VOLATILE_REFRESH_HOURS = 24

        def _age_hours(doc) -> float:
            """Return age of a research doc in hours."""
            created = doc.get("createdAt") if isinstance(doc, dict) else getattr(doc, "createdAt", None)
            if not created:
                return float("inf")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    return float("inf")
            if hasattr(created, "timestamp"):
                return (datetime.utcnow() - created.replace(tzinfo=None)).total_seconds() / 3600
            return float("inf")

        async def _zip_research():
            for zc in zip_codes:
                try:
                    existing = await get_zipcode_report(zc)
                    age_h = _age_hours(existing) if existing else float("inf")

                    if age_h < VOLATILE_REFRESH_HOURS:
                        self._emit("workflow:zipcode_research", f"Zip research for {zc} is fresh ({int(age_h)}h old) — reusing")
                        continue

                    if age_h < FULL_REFRESH_DAYS * 24:
                        # Stable sections still valid — only refresh volatile sections
                        self._emit("workflow:zipcode_research", f"Refreshing volatile sections for {zc} ({int(age_h)}h old)")
                        await research_zip_code(zc, force=True)
                    else:
                        # Full refresh needed (no existing research or stale)
                        age_str = f"{int(age_h)}h old" if age_h != float("inf") else "no existing research"
                        self._emit("workflow:zipcode_research", f"Full research for {zc} ({age_str})")
                        await research_zip_code(zc, force=True)
                except Exception as e:
                    logger.error(f"[WorkflowEngine] Zip code research non-fatal error for {zc}: {e}")

        async def _sector_research():
            try:
                existing = await get_sector_research_for_type(business_type)
                age_h = _age_hours(existing) if existing else float("inf")

                if age_h < FULL_REFRESH_DAYS * 24:
                    self._emit("workflow:sector_research", f"Sector research for {business_type} is fresh ({int(age_h)}h old) — reusing")
                    return

                await run_sector_research(sector=business_type, zip_codes=zip_codes)
                self._emit("workflow:sector_research", f"Sector research completed for {business_type}")
            except Exception as e:
                logger.error(f"[WorkflowEngine] Sector research non-fatal error: {e}")

        async def _area_research():
            try:
                # Check if fresh area research exists for this zip
                existing = await get_area_research_for_zip_code(zip_codes[0])
                age_h = _age_hours(existing) if existing else float("inf")

                if age_h < FULL_REFRESH_DAYS * 24:
                    self._emit("workflow:area_research", f"Area research is fresh ({int(age_h)}h old) — reusing")
                    return

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

        # Inherit URLs from prior runs + search for missing websites BEFORE qualification
        self._emit("workflow:url_resolution", f"Resolving URLs for {len(discovered)} businesses...")
        discovered = await _inherit_urls_from_firestore(discovered)
        discovered = await _find_missing_websites(discovered)

        with_url = sum(1 for b in discovered if b.get("officialUrl"))
        self._emit("workflow:url_resolution", f"URL resolution done: {with_url}/{len(discovered)} have websites")

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

        # Batch insights generation for all analyzed businesses
        analyzed_slugs = [
            b.slug for b in self.workflow.businesses
            if b.phase == BusinessPhase.ANALYSIS_DONE and b.capabilitiesCompleted
        ]
        if analyzed_slugs:
            try:
                from hephae_agents.insights.insights_agent import generate_insights_batch
                self._emit("workflow:batch_insights", f"Generating insights for {len(analyzed_slugs)} businesses (batch)")
                await generate_insights_batch(analyzed_slugs)
                self._emit("workflow:batch_insights_done", f"Batch insights complete for {len(analyzed_slugs)} businesses")
            except Exception as e:
                logger.error(f"[WorkflowEngine] Batch insights error: {e}")

        # Batch synthesis — traffic forecaster + competitive positioning
        if analyzed_slugs:
            try:
                await self._batch_synthesis(analyzed_slugs)
            except Exception as e:
                logger.error(f"[WorkflowEngine] Batch synthesis error: {e}")

    async def _batch_synthesis(self, analyzed_slugs: list[str]):
        """Batch traffic synthesis + competitive positioning for all analyzed businesses.

        Reads deferred intel from task metadata, builds prompts, submits as one batch,
        and writes final outputs to Firestore latestOutputs.
        """
        from hephae_db.firestore.tasks import list_active_tasks_for_businesses
        from hephae_api.workflows.batch_runner import (
            build_traffic_synthesis_prompt,
            build_competitive_positioning_prompt,
            run_synthesis_batch,
        )
        from hephae_api.workflows.capabilities.registry import get_capability
        from hephae_common.firebase import get_db

        db = get_db()

        # Collect deferred synthesis data from task metadata
        tasks = await list_active_tasks_for_businesses(analyzed_slugs)
        deferred_by_slug: dict[str, dict] = {}
        for task in tasks:
            slug = task.get("businessId") or task.get("metadata", {}).get("slug", "")
            meta = task.get("metadata", {})
            ds = meta.get("deferredSynthesis")
            if ds and slug:
                deferred_by_slug[slug] = ds

        if not deferred_by_slug:
            logger.info("[WorkflowEngine] No deferred synthesis data found — skipping batch synthesis")
            return

        # Build batch prompts
        batch_items: list[dict] = []
        for slug, deferred in deferred_by_slug.items():
            if "traffic" in deferred:
                batch_items.append({
                    "request_id": f"traffic:{slug}",
                    "prompt": build_traffic_synthesis_prompt(deferred["traffic"]),
                })
            if "competitive" in deferred:
                batch_items.append({
                    "request_id": f"competitive:{slug}",
                    "prompt": build_competitive_positioning_prompt(deferred["competitive"]),
                })

        if not batch_items:
            return

        self._emit(
            "workflow:batch_synthesis",
            f"Synthesizing traffic + competitive for {len(deferred_by_slug)} businesses ({len(batch_items)} prompts)",
        )

        results = await run_synthesis_batch(batch_items)

        # Fallback: if batch returned None (below threshold), run sequentially
        if results is None:
            from hephae_common.gemini_batch import batch_generate
            prompts = [{"request_id": i["request_id"], "prompt": i["prompt"]} for i in batch_items]
            results = await batch_generate(prompts=prompts, timeout_seconds=300)

        if not results:
            logger.warning("[WorkflowEngine] Batch synthesis returned no results")
            return

        # Write results to Firestore latestOutputs
        traffic_cap = get_capability("traffic")
        competitive_cap = get_capability("competitive")

        for request_id, parsed in results.items():
            if not parsed or isinstance(parsed, dict) and "raw_text" in parsed:
                logger.warning(f"[WorkflowEngine] Synthesis failed for {request_id}")
                continue

            cap_type, slug = request_id.split(":", 1)
            try:
                if cap_type == "traffic" and traffic_cap:
                    adapted = traffic_cap.response_adapter(parsed)
                    await asyncio.to_thread(
                        db.collection("businesses").document(slug).update,
                        {f"latestOutputs.{traffic_cap.firestore_output_key}": adapted, "updatedAt": datetime.utcnow()},
                    )
                elif cap_type == "competitive" and competitive_cap:
                    adapted = competitive_cap.response_adapter(parsed)
                    await asyncio.to_thread(
                        db.collection("businesses").document(slug).update,
                        {f"latestOutputs.{competitive_cap.firestore_output_key}": adapted, "updatedAt": datetime.utcnow()},
                    )
            except Exception as e:
                logger.error(f"[WorkflowEngine] Failed to persist synthesis for {request_id}: {e}")

        self._emit("workflow:batch_synthesis_done", f"Batch synthesis complete ({len(results)} results)")

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
