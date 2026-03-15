"""
Strategic Judge — High-Fidelity Tier 1 Evals.

Uses an LLM Judge to evaluate the semantic quality and strategic
depth of Competitive Analysis and Social Media Audit outputs.
"""

from __future__ import annotations

import json
import logging
import pytest
import pytest_asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents import LlmAgent

from hephae_common.model_config import AgentModels
from hephae_common.adk_helpers import user_msg
from hephae_db.schemas.agent_outputs import EvaluationOutput

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Strategic Judge Agent Definition
# ------------------------------------------------------------------

StrategicJudgeAgent = LlmAgent(
    name="strategic_judge",
    model=AgentModels.PRIMARY_MODEL,
    description="Evaluates the strategic depth of marketing/competitive analysis reports.",
    instruction="""You are a Senior Marketing Strategist. Your job is to review a generated report for a business.
Evaluate based on three criteria (1-10 each):
1. SPECIFICITY: Is the advice tailored to this exact business, or could it apply to anyone?
2. ACTIONABILITY: Are the next steps clear and measurable?
3. RELEVANCE: Does it actually address the competitors and context provided?

Output MUST STRICTLY match this JSON schema:
{
    "score": number (Overall score 0-100),
    "isHallucinated": boolean,
    "issues": string[] (Mention if advice is too generic)
}""",
    output_schema=EvaluationOutput,
)

@pytest_asyncio.fixture
async def strategic_judge():
    """Returns a function that uses StrategicJudgeAgent to grade strategic quality."""
    
    async def _judge(business_context: str, actual_output: dict) -> dict:
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="judge-service",
            agent=StrategicJudgeAgent,
            session_service=session_service,
        )
        user_id = "test-judge"
        session_id = "judge-session"
        
        await session_service.create_session(
            app_name="judge-service", user_id=user_id, session_id=session_id, state={}
        )
        
        prompt = (
            f"BUSINESS_CONTEXT: {business_context}\n"
            f"ACTUAL_OUTPUT: {json.dumps(actual_output)}"
        )
        
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
            import re
            clean = re.sub(r"```json\n?|\n?```", "", final_text).strip()
            return json.loads(clean)
        except Exception as e:
            return {"score": 0, "isHallucinated": True, "issues": [f"Parsing error: {e}"]}

    return _judge

# ------------------------------------------------------------------
# Strategy Quality Tests
# ------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_competitive_strategy_quality(strategic_judge):
    """Verify the strategic depth of Competitive Analysis."""
    from hephae_agents.competitive_analysis.runner import run_competitive_analysis
    
    identity = {
        "name": "Joe's Pizza",
        "address": "Greenwich Village, NYC",
        "competitors": [{"name": "Bleecker Street Pizza"}, {"name": "John's of Bleecker St"}]
    }
    
    # 1. Run real agent logic
    report = await run_competitive_analysis(identity)
    assert report, "Competitive Analysis returned empty report"
    
    # 2. Judge the strategy
    eval_result = await strategic_judge(f"NYC Pizza Shop: {identity['name']}", report)
    
    logger.info(f"Strategic Judge Result: {eval_result}")
    
    # Assertions
    assert eval_result["score"] >= 75, f"Strategy quality too low: {eval_result.get('issues')}"
    # Check if judge flagged generic advice
    assert not any("generic" in issue.lower() for issue in eval_result.get("issues", [])), \
        f"Strategy was flagged as too generic: {eval_result.get('issues')}"

@pytest.mark.integration
@pytest.mark.asyncio
async def test_social_media_strategy_quality(strategic_judge):
    """Verify the strategic depth of Social Media Audit."""
    from hephae_agents.social.media_auditor.runner import run_social_media_audit
    
    identity = {
        "name": "Katz's Delicatessen",
        "address": "LES, NYC",
        "socialLinks": {"instagram": "https://www.instagram.com/katzsdeli/"}
    }
    
    report = await run_social_media_audit(identity)
    assert report, "Social Audit returned empty report"
    
    eval_result = await strategic_judge(f"Iconic NYC Deli: {identity['name']}", report)
    
    assert eval_result["score"] >= 75, f"Social strategy quality too low: {eval_result.get('issues')}"
