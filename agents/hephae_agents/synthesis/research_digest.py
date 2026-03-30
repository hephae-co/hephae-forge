"""Research Digest ADK agents — synthesize all research references, citations,
and external studies into a structured knowledge digest per vertical.

Pipeline: ResearchDataLoader (BaseAgent) → ResearchSynthesizer (LlmAgent) → ResearchDigestAssembler (BaseAgent)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types as genai_types

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


class ResearchDataLoader(BaseAgent):
    """Load all research references, citations, and guides for a vertical."""

    name: str = "ResearchDataLoader"
    description: str = "Loads research references and external studies from data_cache."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        vertical = state.get("vertical", "")
        week_of = state.get("weekOf", "")

        logger.info(f"[ResearchDigest] Loading research data for {vertical} ({week_of})")

        from hephae_common.firebase import get_db
        db = get_db()

        # Load all research_reference entries from data_cache
        references: list[dict] = []
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            docs = await asyncio.to_thread(
                lambda: list(db.collection("data_cache").where(
                    filter=FieldFilter("source", "==", "research_reference")
                ).get())
            )
            for doc in docs:
                data = doc.to_dict().get("data", {})
                topics = data.get("topics", [])
                # Include if relevant to this vertical or general
                if vertical in topics or "small_business" in topics or "ai_tools" in topics or "guide" in topics:
                    references.append(data)
        except Exception as e:
            logger.warning(f"[ResearchDigest] Failed to load references: {e}")

        # Load research index if available
        try:
            idx_doc = await asyncio.to_thread(
                db.collection("data_cache").document(f"research_index:genai-smb-citations-{week_of}").get
            )
            if idx_doc.exists:
                idx_data = idx_doc.to_dict().get("data", {})
                state_delta_extra = {"researchIndex": idx_data}
            else:
                state_delta_extra = {}
        except Exception:
            state_delta_extra = {}

        # Load the guide metadata if available
        guide_meta = None
        try:
            guide_doc = await asyncio.to_thread(
                db.collection("data_cache").document("research_guide:genai-tools-smb-2026").get
            )
            if guide_doc.exists:
                guide_meta = guide_doc.to_dict().get("data", {})
        except Exception:
            pass

        # Load zipcode research for context (if we have registered zips)
        zip_research_facts: list[str] = []
        try:
            from hephae_db.firestore.registered_zipcodes import list_registered_zipcodes
            active_zips = await list_registered_zipcodes(status="active")
            for reg in active_zips[:3]:  # sample up to 3 zips
                zc = reg.get("zipCode", "")
                if zc:
                    results = await asyncio.to_thread(
                        lambda z=zc: list(db.collection("zipcode_research").where(
                            filter=FieldFilter("zipCode", "==", z)
                        ).limit(1).get())
                    )
                    if results:
                        report = results[0].to_dict().get("report", {})
                        sections = report.get("sections", {})
                        for sec_key in ["business_landscape", "consumer_market"]:
                            sec = sections.get(sec_key, {})
                            if isinstance(sec, dict):
                                zip_research_facts.extend(sec.get("key_facts", [])[:2])
        except Exception:
            pass

        logger.info(f"[ResearchDigest] Loaded {len(references)} references, {len(zip_research_facts)} zip facts")

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={
                "rawReferences": references,
                "guideMeta": guide_meta or {},
                "zipResearchFacts": zip_research_facts,
                **state_delta_extra,
            }),
        )


RESEARCH_SYNTH_INSTRUCTION = """You are a research analyst synthesizing external studies, guides, and citations
into an actionable research digest for the {vertical} industry.

Given the research references and data below, write:

1. **landscape** (2-3 paragraphs): The current state of AI/technology adoption in this vertical.
   What are the key trends, adoption rates, and pain points? Cite specific studies and numbers.

2. **keyFindings** (5-7 bullet points): The most important discoveries from the research.
   Each should be specific, cite a source, and be actionable for a business owner.

3. **gapAnalysis** (2-3 bullets): What's NOT covered by existing research — areas where
   we have gaps in our knowledge for this vertical.

4. **recommendedReading** (3-5 items): The most valuable references for a business owner
   in this vertical, with a one-line reason why.

Return as JSON: {"landscape": "...", "keyFindings": ["..."], "gapAnalysis": ["..."], "recommendedReading": [{"title": "...", "url": "...", "reason": "..."}]}
"""


def _research_synth_before_model(callback_context: Any, llm_request: Any) -> None:
    state = callback_context.state
    refs = state.get("rawReferences", [])
    guide = state.get("guideMeta", {})
    zip_facts = state.get("zipResearchFacts", [])
    vertical = state.get("vertical", "unknown")

    parts = []

    if guide:
        parts.append(f"Guide Overview: {guide.get('title', '')} — {guide.get('toolCount', '?')} tools cataloged")
        if guide.get("keyStats"):
            stats = guide["keyStats"]
            parts.append(f"Key Stats: adoption={stats.get('smb_ai_adoption')}, avg spend={stats.get('avg_spend')}, ROI={stats.get('roi')}")

    if refs:
        ref_text = "\n".join(
            f"- [{r.get('title', '?')}]({r.get('url', '')}) — {r.get('summary', '')[:120]}"
            for r in refs[:20]
        )
        parts.append(f"Research References ({len(refs)}):\n{ref_text}")

    if zip_facts:
        parts.append(f"Local Market Facts:\n" + "\n".join(f"- {f}" for f in zip_facts[:6]))

    context = "\n\n".join(parts) if parts else "Limited research data available."

    instruction = RESEARCH_SYNTH_INSTRUCTION.replace("{vertical}", vertical)
    llm_request.config = llm_request.config or genai_types.GenerateContentConfig()
    llm_request.config.system_instruction = instruction

    llm_request.contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=context)])
    )


class ResearchDigestAssembler(BaseAgent):
    name: str = "ResearchDigestAssembler"
    description: str = "Assembles the final research digest document."

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        synth_raw = state.get("synthOutput", "")
        refs = state.get("rawReferences", [])

        import re
        landscape = ""
        key_findings: list[str] = []
        gap_analysis: list[str] = []
        recommended_reading: list[dict] = []

        try:
            json_match = re.search(r'\{[\s\S]*\}', synth_raw)
            if json_match:
                parsed = json.loads(json_match.group())
                landscape = parsed.get("landscape", synth_raw)
                key_findings = parsed.get("keyFindings", [])
                gap_analysis = parsed.get("gapAnalysis", [])
                recommended_reading = parsed.get("recommendedReading", [])
            else:
                landscape = synth_raw
        except (json.JSONDecodeError, AttributeError):
            landscape = synth_raw

        digest = {
            "landscape": landscape,
            "keyFindings": key_findings[:7],
            "gapAnalysis": gap_analysis[:3],
            "recommendedReading": recommended_reading[:5],
            "totalReferences": len(refs),
            "referenceUrls": [r.get("url") for r in refs if r.get("url")][:20],
        }

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"researchDigest": digest}),
        )


def create_research_digest_agent() -> SequentialAgent:
    return SequentialAgent(
        name="ResearchDigestPipeline",
        sub_agents=[
            ResearchDataLoader(),
            LlmAgent(
                name="ResearchSynthesizer",
                model=AgentModels.PRIMARY_MODEL,
                instruction=RESEARCH_SYNTH_INSTRUCTION,
                before_model_callback=_research_synth_before_model,
                output_key="synthOutput",
                on_model_error_callback=fallback_on_error,
            ),
            ResearchDigestAssembler(),
        ],
    )
