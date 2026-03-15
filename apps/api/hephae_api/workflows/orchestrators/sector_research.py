"""Sector research orchestrator — industry analysis + local trends + synthesis."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from hephae_agents.research.industry_analyst import analyze_industry
from hephae_agents.research.local_sector_trends import analyze_local_sector_trends
from hephae_agents.research.area_summary import generate_area_summary
from hephae_db.firestore.research import create_sector_research, save_sector_research, load_sector_research
from hephae_db.firestore.research import get_zipcode_report
from hephae_api.types import SectorResearchDocument, SectorResearchPhase

logger = logging.getLogger(__name__)


async def run_sector_research(
    sector: str,
    zip_codes: list[str],
    area_name: str | None = None,
) -> SectorResearchDocument:
    """Run the full sector research pipeline.

    1. Analyze industry at national level
    2. Analyze local sector trends per zip code
    3. Synthesize into summary
    """
    doc = await create_sector_research(sector, zip_codes, area_name)

    try:
        # Phase 1: Industry analysis
        doc.phase = SectorResearchPhase.ANALYZING
        await save_sector_research(doc)

        logger.info(f"[SectorResearch] Analyzing industry: {sector}")
        industry_analysis = await analyze_industry(sector)

        # Phase 2: Local trends per zip
        doc.phase = SectorResearchPhase.LOCAL_TRENDS
        await save_sector_research(doc)

        local_trends = []
        for zip_code in zip_codes:
            try:
                report_doc = await get_zipcode_report(zip_code)
                if not report_doc:
                    continue
                report = report_doc.report
                report_dict = report.model_dump(mode="json") if hasattr(report, "model_dump") else report

                logger.info(f"[SectorResearch] Analyzing local trends for {zip_code}")
                trends = await analyze_local_sector_trends(zip_code, sector, report_dict)
                local_trends.append(trends)
            except Exception as e:
                logger.error(f"[SectorResearch] Local trends failed for {zip_code}: {e}")

        # Phase 3: Synthesis
        doc.phase = SectorResearchPhase.SYNTHESIZING
        await save_sector_research(doc)

        # Build synthesis using area summary agent
        zip_reports = []
        for zip_code in zip_codes:
            try:
                report_doc = await get_zipcode_report(zip_code)
                if report_doc:
                    report = report_doc.report
                    zip_reports.append(report.model_dump(mode="json") if hasattr(report, "model_dump") else report)
            except Exception:
                pass

        synthesis = None
        if zip_reports:
            try:
                synthesis = await generate_area_summary(sector, zip_reports)
            except Exception as e:
                logger.error(f"[SectorResearch] Synthesis failed: {e}")

        # Build summary
        summary = {
            "industryAnalysis": industry_analysis,
            "localTrends": local_trends,
            "synthesis": synthesis or {
                "narrative": f"Sector research for {sector} across {len(zip_codes)} zip codes.",
                "sectorHealthScore": 0,
                "localFitScore": 0,
                "topInsights": [],
                "strategicRecommendations": [],
            },
            "generatedAt": datetime.utcnow().isoformat(),
        }

        doc.summary = summary
        doc.phase = SectorResearchPhase.COMPLETED
        await save_sector_research(doc)

        logger.info(f"[SectorResearch] Complete for {sector}")
        return doc

    except Exception as e:
        logger.error(f"[SectorResearch] Fatal error: {e}")
        doc.phase = SectorResearchPhase.FAILED
        doc.lastError = str(e)
        await save_sector_research(doc)
        return doc
