"""
High-Fidelity Tier 1 Evals — Semantic Judging.

Uses SeoEvaluatorAgent to judge the ACTUAL content and quality
of agent outputs, moving beyond simple structural validation.
"""

from __future__ import annotations

import json
import logging
import pytest
import pytest_asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_agents.seo_auditor.runner import run_seo_audit
from hephae_agents.evaluators.seo_evaluator import SeoEvaluatorAgent
from hephae_common.adk_helpers import user_msg

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Semantic Judge Fixture
# ------------------------------------------------------------------

@pytest_asyncio.fixture
async def semantic_judge():
    """Returns a function that uses SeoEvaluatorAgent to grade an output."""
    
    async def _judge(target_url: str, actual_output: dict) -> dict:
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="judge-service",
            agent=SeoEvaluatorAgent,
            session_service=session_service,
        )
        user_id = "test-judge"
        session_id = "judge-session"
        
        await session_service.create_session(
            app_name="judge-service", user_id=user_id, session_id=session_id, state={}
        )
        
        prompt = (
            f"TARGET_URL: {target_url}\n"
            f"ACTUAL_OUTPUT: {json.dumps(actual_output)}"
        )
        
        # Collect final output
        final_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(prompt),
        ):
            content = getattr(event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "text", None) and not getattr(part, "thought", False):
                        final_text += part.text
        
        try:
            # ADK response_schema handles the cleanup usually, but we'll be safe
            import re
            clean = re.sub(r"```json\n?|\n?```", "", final_text).strip()
            return json.loads(clean)
        except Exception as e:
            logger.error(f"Judge failed to parse JSON: {final_text}")
            return {"score": 0, "isHallucinated": True, "issues": [f"Parsing error: {e}"]}

    return _judge


# ------------------------------------------------------------------
# Quality Tests
# ------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_seo_audit_quality_high_fidelity(semantic_judge):
    """Run real SEO audit and use the Semantic Judge to verify quality."""
    identity = {
        "name": "Nom Wah Tea Parlor",
        "officialUrl": "https://nomwah.com/",
        "category": "Dim Sum Restaurant"
    }
    
    # 1. Run the real agent logic (calls Gemini + Tools)
    report = await run_seo_audit(identity)
    assert report, "SEO Auditor returned empty report"
    assert "sections" in report, "SEO Report missing sections"
    
    # 2. Use the Semantic Judge to grade the content
    eval_result = await semantic_judge(identity["officialUrl"], report)
    
    logger.info(f"Judge Result: {eval_result}")
    
    # Assertions based on semantic quality
    assert eval_result["score"] >= 70, f"SEO Audit quality too low: {eval_result.get('issues')}"
    assert not eval_result["isHallucinated"], f"Hallucination detected: {eval_result.get('issues')}"


@pytest.mark.asyncio
async def test_judge_detects_hallucinations(semantic_judge):
    """Verify that the judge itself is working by passing it garbage data."""
    target_url = "https://nomwah.com/"
    
    # Purposely hallucinated data: describing a dental office for a tea parlor URL
    hallucinated_report = {
        "overallScore": 95,
        "summary": "This dental office has excellent SEO for wisdom tooth extraction.",
        "sections": [
            {
                "title": "Technical SEO",
                "score": 90,
                "description": "The site is perfectly optimized for 'dentist NYC' keywords."
            }
        ]
    }
    
    eval_result = await semantic_judge(target_url, hallucinated_report)
    
    # The judge should catch this mismatch
    assert eval_result["isHallucinated"] or eval_result["score"] < 50, \
        "Judge failed to catch obvious hallucination/mismatch"
    assert any("dental" in issue.lower() or "dentist" in issue.lower() or "tea" in issue.lower() 
               for issue in eval_result.get("issues", [])), \
        f"Judge didn't flag the dental/tea mismatch correctly: {eval_result.get('issues')}"
