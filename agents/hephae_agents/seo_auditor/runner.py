"""SEO Auditor runner — stateless async function.

Runs the SEO auditor agent with native structured output (output_schema).
Returns the parsed SEO report dict.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_helpers import user_msg, _strip_markdown_fences

from hephae_agents.seo_auditor.agent import seo_auditor_agent
from hephae_agents.seo_auditor.prompt import SEO_AUDITOR_INSTRUCTION
from hephae_agents.seo_auditor.tools import pagespeed_tool
from hephae_agents.shared_tools import google_search_tool
from hephae_db.schemas.agent_outputs import SeoAuditorOutput

logger = logging.getLogger(__name__)


def _try_parse_json(source: str) -> dict | None:
    """Parse JSON from agent output, with fallback for markdown fences."""
    if not source:
        return None
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        pass
    # Fallback: strip markdown fences if model didn't honor output_schema
    clean = _strip_markdown_fences(source)
    fb = clean.find("{")
    lb = clean.rfind("}")
    if fb == -1 or lb <= fb:
        return None
    clean = clean[fb : lb + 1]
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        try:
            return json.loads(re.sub(r",\s*([\]}])", r"\1", clean))
        except json.JSONDecodeError:
            return None


def _is_final_response(event) -> bool:
    content = getattr(event, "content", None)
    if not content or not hasattr(content, "parts"):
        return False
    for part in content.parts:
        if hasattr(part, "function_call") and part.function_call:
            return False
        if hasattr(part, "function_response") and part.function_response:
            return False
    return True


def _has_valid_sections(report_data: dict) -> bool:
    sections = report_data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        return False
    return any(isinstance(s, dict) and s.get("score", 0) > 0 for s in sections)


async def _run_seo_agent(agent, identity: dict, memory_service=None, session_service=None) -> dict:
    """Run an SEO auditor agent and return the parsed report data (or {})."""
    session_service = session_service or InMemorySessionService()
    runner = Runner(
        app_name="hephae-hub",
        agent=agent,
        session_service=session_service,
        memory_service=memory_service,
    )

    session_id = f"seo-{int(time.time() * 1000)}"
    user_id = "hub-user"

    await session_service.create_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id, state={}
    )

    text_buffer = ""
    final_response_text = ""
    thought_buffer = ""

    async for raw_event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg(
            f"Execute a full SEO Deep Dive on {identity['officialUrl']}. "
            "Evaluate technical SEO, content quality, user experience, performance, and backlinks."
        ),
    ):
        content = getattr(raw_event, "content", None)
        if content and hasattr(content, "parts"):
            for part in content.parts:
                if getattr(part, "thought", False):
                    if getattr(part, "text", None):
                        thought_buffer += part.text
                    continue
                if getattr(part, "text", None):
                    text_buffer += part.text

            if _is_final_response(raw_event):
                for part in content.parts:
                    if getattr(part, "text", None) and not getattr(part, "thought", False):
                        final_response_text += part.text

    logger.info(
        f"[SEO Runner] Stream drained: buffer={len(text_buffer)} chars, "
        f"finalResponse={len(final_response_text)} chars, thought={len(thought_buffer)} chars"
    )

    # With output_schema on the agent, the final response should be valid JSON
    return (
        _try_parse_json(final_response_text)
        or _try_parse_json(text_buffer)
        or _try_parse_json(thought_buffer)
        or {}
    )


async def run_seo_audit(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run a full SEO audit with fallback model support.

    Args:
        identity: Enriched identity dict (must have officialUrl).
        business_context: Optional BusinessContext (unused currently, reserved).

    Returns:
        SEO report dict with sections, overallScore, url, etc.
    """
    if not identity.get("officialUrl"):
        raise ValueError("No URL available for SEO Audit.")

    logger.info(f"[SEO Runner] Launching for {identity['officialUrl']}...")

    # Track 2: Load semantic few-shot examples from Vertex AI Example Store
    examples_context = ""
    try:
        from hephae_db.eval.example_store import example_store
        examples = await example_store.retrieve_examples(
            store_id="seo-auditor-store",
            query=f"Business: {identity.get('name')}, Category: {identity.get('category')}"
        )
        if examples:
            examples_context = "\n### REFERENCE GOLD-STANDARD EXAMPLES:\n"
            for i, ex in enumerate(examples):
                examples_context += f"Example {i+1}:\nInput: {ex['input']}\nOutput: {ex['output']}\n\n"
    except Exception as e:
        logger.warning(f"[SEO Runner] Failed to retrieve examples: {e}")

    # Load grounding memory from human-curated fixtures (few-shot examples)
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("seo_auditor")

    # Inject examples into identity for the agent to see
    identity_with_examples = {**identity, "examples_context": examples_context}

    # Primary run with ENHANCED model
    ext_session_service = kwargs.get("session_service")
    report_data = await _run_seo_agent(seo_auditor_agent, identity_with_examples, memory_service, session_service=ext_session_service)

    # Fallback: if primary model returned empty/useless sections, retry with lite model
    if not _has_valid_sections(report_data):
        logger.warning(
            f"[SEO Runner] Primary model returned empty sections for {identity['officialUrl']}. "
            f"Retrying with fallback model {AgentModels.FALLBACK_MODEL}..."
        )
        from google.adk.tools.load_memory_tool import load_memory_tool
        fallback_agent = LlmAgent(
            name="seoAuditorFallback",
            description="SEO Auditor (fallback model)",
            instruction=SEO_AUDITOR_INSTRUCTION,
            model=AgentModels.FALLBACK_MODEL,
            tools=[google_search_tool, pagespeed_tool, load_memory_tool],
            on_model_error_callback=fallback_on_error,
        )
        fallback_data = await _run_seo_agent(fallback_agent, identity, memory_service, session_service=ext_session_service)
        if _has_valid_sections(fallback_data):
            report_data = fallback_data
            logger.info("[SEO Runner] Fallback model produced valid sections.")
        else:
            logger.warning("[SEO Runner] Fallback model also returned empty sections.")
            if fallback_data.get("overallScore"):
                report_data = fallback_data

    if not report_data:
        logger.error("[SEO Runner] All JSON extraction failed.")

    # Mark sections as analyzed
    if isinstance(report_data.get("sections"), list):
        for section in report_data["sections"]:
            if not isinstance(section, dict):
                continue
            section["isAnalyzed"] = True
            if not isinstance(section.get("recommendations"), list):
                section["recommendations"] = []
            else:
                section["recommendations"] = [
                    r for r in section["recommendations"] if isinstance(r, dict)
                ]

    return {
        **report_data,
        "url": identity["officialUrl"],
        "sections": [s for s in report_data.get("sections", []) if isinstance(s, dict)]
        if isinstance(report_data.get("sections"), list)
        else [],
    }
