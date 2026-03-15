"""
DispatcherAgent — the "Brain" of background task execution.

Instead of hardcoded loops, this agent decides which actions are 
actually needed based on the current business state.
"""

from __future__ import annotations

import logging
from google.adk.agents import LlmAgent
from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

DISPATCHER_INSTRUCTION = """You are a Workflow Orchestrator. 
Your job is to decide the next best sequence of agentic actions for a business.

You will be given:
1. The requested target action (e.g., "ANALYZE_FULL").
2. The current business state (what data we already have).

RULES:
- If we already have fresh data (< 7 days old) for a requested sub-step, SKIP it.
- If we are missing "Identity" data, always run ENRICH first.
- If the target is "ANALYZE_FULL", you can trigger: SEO, MARGIN, SOCIAL, TRAFFIC, COMPETITIVE.

Return a JSON plan:
{
  "actions": [
    { "type": "ENRICH" | "SEO" | "MARGIN" | "SOCIAL" | "TRAFFIC" | "COMPETITIVE" | "INSIGHTS", "priority": 1-10 }
  ],
  "rationale": "Reason for choosing this sequence."
}"""

DispatcherAgent = LlmAgent(
    name="workflow_dispatcher",
    model=AgentModels.PRIMARY_MODEL,
    instruction=DISPATCHER_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)

async def plan_workflow(business_id: str, target_action: str) -> dict:
    """Agentically decide which sub-tasks to trigger."""
    from hephae_db.firestore.businesses import get_business
    biz = await get_business(business_id)
    
    # Construct a state summary for the dispatcher
    outputs = biz.get("latestOutputs", {})
    state = {
        "has_identity": bool(biz.get("identity")),
        "last_seo": outputs.get("seo_auditor", {}).get("runAt"),
        "last_margin": outputs.get("margin_surgeon", {}).get("runAt"),
        "target": target_action
    }
    
    prompt = f"BUSINESS: {biz['name']}\nSTATE: {state}"
    
    plan = await run_agent_to_json(DispatcherAgent, prompt, app_name="dispatcher")
    return plan or {"actions": [{"type": target_action, "priority": 5}], "rationale": "Fallback to manual target."}
