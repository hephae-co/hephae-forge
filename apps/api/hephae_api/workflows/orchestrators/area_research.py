"""Area research orchestrator — multi-phase pipeline for area-level analysis."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Callable

from hephae_agents.discovery.county_resolver import resolve_county_zip_codes
from hephae_agents.discovery.municipal_hubs import find_municipal_hub
from hephae_agents.discovery.directory_parser import parse_directory_content
from hephae_agents.shared_tools import crawl4ai_tool
from hephae_agents.research.area_summary import generate_area_summary, generate_enhanced_area_summary
from hephae_agents.research.intel_fan_out import gather_intelligence
from hephae_agents.research.local_sector_trends import analyze_local_sector_trends
from hephae_db.firestore.research import create_area_research, save_area_research, load_area_research
from hephae_db.firestore.research import get_zipcode_report, get_run
from hephae_integrations.fda_client import is_food_related_industry
from hephae_api.workflows.orchestrators.zipcode_research import research_zip_code
from hephae_api.types import AreaResearchDocument, AreaResearchPhase, AreaResearchProgress, AreaResearchProgressEvent

logger = logging.getLogger(__name__)

# In-memory registry for SSE streaming
_active_orchestrators: dict[str, "AreaResearchOrchestrator"] = {}


def get_active_orchestrator(area_id: str) -> "AreaResearchOrchestrator | None":
    return _active_orchestrators.get(area_id)


class AreaResearchOrchestrator:
    def __init__(self, doc: AreaResearchDocument, max_zip_codes: int = 10):
        self.doc = doc
        self.max_zip_codes = max_zip_codes
        self._listeners: set[Callable[[AreaResearchProgressEvent], None]] = set()

    def add_listener(self, fn: Callable[[AreaResearchProgressEvent], None]):
        self._listeners.add(fn)

    def remove_listener(self, fn: Callable[[AreaResearchProgressEvent], None]):
        self._listeners.discard(fn)

    def _build_progress(self, current_zip: str | None = None) -> AreaResearchProgress:
        return AreaResearchProgress(
            totalZipCodes=len(self.doc.zipCodes),
            completedZipCodes=len(self.doc.completedZipCodes),
            failedZipCodes=len(self.doc.failedZipCodes),
            currentZipCode=current_zip,
        )

    def _emit(self, event_type: str, message: str, current_zip: str | None = None):
        event = AreaResearchProgressEvent(
            type=event_type,
            areaId=self.doc.id,
            phase=self.doc.phase,
            message=message,
            progress=self._build_progress(current_zip=current_zip),
            timestamp=datetime.utcnow().isoformat(),
        )
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    async def _checkpoint(self):
        await save_area_research(self.doc.model_dump())

    async def run(self):
        _active_orchestrators[self.doc.id] = self

        try:
            # Phase 1: Resolve zip codes
            if not self.doc.zipCodes:
                self.doc.phase = AreaResearchPhase.RESOLVING
                await self._checkpoint()
                self._emit("area:resolving", f'Resolving zip codes for "{self.doc.area}"')

                resolved = await resolve_county_zip_codes(self.doc.area, self.max_zip_codes)
                if not resolved.zipCodes:
                    raise ValueError(resolved.error or f'Could not resolve zip codes for "{self.doc.area}"')

                self.doc.zipCodes = resolved.zipCodes
                self.doc.resolvedCountyName = resolved.countyName
                self.doc.resolvedState = resolved.state
                await self._checkpoint()
                self._emit("area:resolved", f"Resolved {len(resolved.zipCodes)} zip codes for {resolved.countyName}, {resolved.state}")

            # Phase 2: Research each zip code
            self.doc.phase = AreaResearchPhase.RESEARCHING
            await self._checkpoint()

            for zip_code in self.doc.zipCodes:
                if zip_code in self.doc.completedZipCodes or zip_code in self.doc.failedZipCodes:
                    continue

                self._emit("area:zip_research_started", f"Researching zip code {zip_code}", zip_code)

                try:
                    await research_zip_code(zip_code)
                    self.doc.completedZipCodes.append(zip_code)
                    self._emit("area:zip_research_done", f"Completed research for {zip_code}", zip_code)
                except Exception as e:
                    logger.error(f"[AreaResearch] Failed for {zip_code}: {e}")
                    self.doc.failedZipCodes.append(zip_code)
                    self._emit("area:zip_research_failed", f"Failed: {zip_code} — {e}", zip_code)

                await self._checkpoint()

            if not self.doc.completedZipCodes:
                raise ValueError("All zip code research attempts failed")

            # Phase 3: Industry intelligence (parallel)
            if not self.doc.industryIntel:
                self.doc.phase = AreaResearchPhase.INDUSTRY_INTEL
                await self._checkpoint()
                self._emit("area:industry_intel", f"Gathering industry intelligence for {self.doc.businessType}...")

                intel = await self._gather_industry_intelligence()
                self.doc.industryIntel = intel
                await self._checkpoint()
                self._emit("area:industry_intel_done", "Industry intelligence gathered")

            # Phase 4: Local sector analysis
            if not self.doc.localSectorInsights:
                self.doc.phase = AreaResearchPhase.LOCAL_SECTOR_ANALYSIS
                await self._checkpoint()
                self._emit("area:local_sector_analysis", f"Analyzing local sector trends for {self.doc.businessType}...")

                insights = await self._analyze_local_sectors()
                self.doc.localSectorInsights = insights
                await self._checkpoint()
                self._emit("area:local_sector_analysis_done", f"Local sector analysis complete ({len(insights.get('trends', []))} zips)")

            # Phase 5: Enhanced synthesis
            self.doc.phase = AreaResearchPhase.SYNTHESIZING
            await self._checkpoint()
            self._emit("area:summarizing", f"Synthesizing all intelligence for {self.doc.businessType}...")

            zip_reports = await self._fetch_zip_reports(self.doc.completedZipCodes)

            intel = self.doc.industryIntel
            has_enhanced = intel and (
                (hasattr(intel, "industryAnalysis") and intel.industryAnalysis)
                or (isinstance(intel, dict) and intel.get("industryAnalysis"))
            )

            intel_dict = intel.model_dump(mode="json") if hasattr(intel, "model_dump") else (intel or {})

            if has_enhanced:
                sector_trends = self.doc.localSectorInsights
                trends_list = sector_trends.get("trends", []) if isinstance(sector_trends, dict) else (sector_trends.trends if hasattr(sector_trends, "trends") else [])

                # Serialize BLS/USDA data for the synthesis agent
                bls_data = intel_dict.get("blsCpiData")
                if bls_data and hasattr(bls_data, "model_dump"):
                    bls_data = bls_data.model_dump(mode="json")
                usda_data = intel_dict.get("usdaPriceData")
                if usda_data and hasattr(usda_data, "model_dump"):
                    usda_data = usda_data.model_dump(mode="json")

                summary = await generate_enhanced_area_summary(
                    business_type=self.doc.businessType,
                    reports=list(zip_reports.values()),
                    industry_analysis=intel_dict.get("industryAnalysis"),
                    industry_news=intel_dict.get("industryNews"),
                    trends_data=intel_dict.get("industryTrends"),
                    fda_data=intel_dict.get("fdaData"),
                    local_sector_trends=trends_list,
                    bls_cpi_data=bls_data,
                    usda_price_data=usda_data,
                    local_catalysts=intel_dict.get("localCatalysts"),
                    demographic_data=intel_dict.get("demographicData"),
                )
            else:
                summary = await generate_area_summary(
                    business_type=self.doc.businessType,
                    reports=list(zip_reports.values()),
                )

            self.doc.summary = summary
            self.doc.phase = AreaResearchPhase.COMPLETED
            await self._checkpoint()
            self._emit("area:completed", "Area research complete")

            # Phase 6: Automatic Lead Discovery (The "Gift of Value")
            leads = []
            try:
                self._emit("area:discovering_leads", f"Discovering official {self.doc.businessType} leads from municipal directories...")
                leads = await self._discover_leads_from_hub()
                if leads:
                    self._emit("area:leads_found", f"Successfully discovered {len(leads)} high-trust leads for {self.doc.businessType}")
            except Exception as e:
                logger.warning(f"[AreaResearch] Automated lead discovery failed: {e}")

            # Phase 7: Batch Supervision (The "Cliffnotes")
            try:
                from hephae_agents.discovery.batch_supervisor import generate_batch_summary
                self._emit("area:supervising", "Generating executive batch summary...")
                
                # Fetch businesses from the unified pool for this area run
                from hephae_db.firestore.businesses import get_businesses_in_area_run
                discovered_businesses = await get_businesses_in_area_run(self.doc.id)
                
                batch_summary = await generate_batch_summary(self.doc.area, discovered_businesses)
                self.doc.summary.automatedBatchSummary = batch_summary
                
                # Final state update for Human-in-the-Loop
                self.doc.phase = AreaResearchPhase.REVIEW_REQUIRED
                await self._checkpoint()
                self._emit("area:ready_for_review", "Batch processing complete. Ready for human approval.")
            except Exception as e:
                logger.warning(f"[AreaResearch] Batch supervision failed: {e}")

        except Exception as e:
            logger.error(f"[AreaResearch] Fatal error for {self.doc.id}: {e}")
            self.doc.phase = AreaResearchPhase.FAILED
            self.doc.lastError = str(e)
            await self._checkpoint()
            self._emit("area:failed", f"Failed: {e}")
        finally:
            _active_orchestrators.pop(self.doc.id, None)

    async def _gather_industry_intelligence(self) -> dict:
        """Gather intelligence using ADK ParallelAgent + API data sources."""
        area = self.doc.resolvedCountyName or self.doc.area
        state = self.doc.resolvedState or ""
        industry = self.doc.businessType
        city = area.split(",")[0].strip() if "," in area else area

        # Extract DMA name from first completed zip report
        dma_name = ""
        try:
            first_zip = self.doc.completedZipCodes[0] if self.doc.completedZipCodes else None
            if first_zip:
                report_doc = await get_zipcode_report(first_zip)
                if report_doc and report_doc.report:
                    report = report_doc.report
                    geo = report.sections.geography if hasattr(report, "sections") else None
                    if geo:
                        content = geo.content if hasattr(geo, "content") else ""
                        match = re.search(r"DMA\s*(?:Region|Name|Area)?\s*:\s*([^\n,.]+)", content, re.IGNORECASE)
                        if match:
                            dma_name = re.sub(r"[*#_`]", "", match.group(1)).strip()
        except Exception:
            pass

        return await gather_intelligence(
            area=area,
            state=state,
            city=city,
            business_type=industry,
            completed_zip_codes=self.doc.completedZipCodes,
            dma_name=dma_name,
            is_food=is_food_related_industry(industry),
            on_progress=lambda msg: self._emit("area:industry_intel_progress", msg),
        )

    async def _analyze_local_sectors(self) -> dict:
        trends = []
        for zip_code in self.doc.completedZipCodes:
            try:
                report_doc = await get_zipcode_report(zip_code)
                if not report_doc:
                    continue

                report = report_doc.report
                report_dict = report.model_dump(mode="json") if hasattr(report, "model_dump") else report

                self._emit("area:local_sector_zip", f"Analyzing sector trends for {zip_code}", zip_code)
                result = await analyze_local_sector_trends(zip_code, self.doc.businessType, report_dict)
                trends.append(result)
            except Exception as e:
                logger.error(f"[AreaResearch] Local sector analysis failed for {zip_code}: {e}")

        return {"trends": trends}

    async def _discover_leads_from_hub(self) -> list[dict]:
        """Find the municipal hub, crawl it, and save businesses to Firestore."""
        city = self.doc.area.split(",")[0].strip() if "," in self.doc.area else self.doc.area
        state = self.doc.resolvedState or ""
        
        # 1. Find the Hub
        hub_url = await find_municipal_hub(city, state)
        if not hub_url:
            logger.info(f"[AreaResearch] No municipal hub found for {city}, {state}")
            return []

        # 2. Crawl it
        try:
            crawl_result = await crawl4ai_tool(hub_url)
            content = crawl_result.get("markdown") or crawl_result.get("text", "")
            if not content:
                return []

            # 3. Parse leads
            raw_leads = await parse_directory_content(content, category=self.doc.businessType)
            
            # 4. Save to Firestore (Unified Lead Pool)
            from hephae_db.firestore.businesses import save_business
            from hephae_api.workflows.phases.discovery import generate_slug
            
            final_leads = []
            for lead in raw_leads:
                slug = generate_slug(lead["name"])
                await save_business(slug, {
                    **lead,
                    "discoveryStatus": "hub_scanned",
                    "sourceAreaId": self.doc.id,
                    "updatedAt": datetime.utcnow()
                })
                final_leads.append(lead)
                
            return final_leads
        except Exception as e:
            logger.error(f"[AreaResearch] Lead discovery crawl failed: {e}")
            return []

    async def _fetch_zip_reports(self, zip_codes: list[str]) -> dict[str, dict]:
        reports = {}
        for zip_code in zip_codes:
            try:
                report_doc = await get_zipcode_report(zip_code)
                if report_doc:
                    report = report_doc.report
                    reports[zip_code] = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
            except Exception:
                logger.error(f"[AreaResearch] Could not fetch report for {zip_code}")
        return reports

    def get_document(self) -> AreaResearchDocument:
        return self.doc


async def start_area_research(
    area: str,
    business_type: str,
    max_zip_codes: int = 10,
) -> dict:
    """Start area research in background. Returns {"orchestrator": ..., "areaId": str}."""
    raw = await create_area_research(area, business_type, [])
    doc = AreaResearchDocument(**raw)
    orchestrator = AreaResearchOrchestrator(doc, max_zip_codes)

    # Run in background
    asyncio.create_task(orchestrator.run())

    return {"orchestrator": orchestrator, "areaId": doc.id}
