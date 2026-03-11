"""
Toolified Capabilities — wraps runners as ADK AgentTools.

This implements the P1.1 Hub-and-Spoke architecture, allowing the 
DispatcherAgent to manage capabilities as a list of dynamic tools.
"""

from __future__ import annotations

from google.adk.tools import FunctionTool
from backend.workflows.capabilities.registry import get_capability

def get_capability_tool(name: str) -> FunctionTool | None:
    """Wrap a registered capability into an ADK FunctionTool."""
    cap = get_capability(name)
    if not cap:
        return None

    async def _tool_fn(business_id: str) -> dict:
        """The actual function called by the LLM."""
        from hephae_db.firestore.businesses import get_business
        biz = await get_business(business_id)
        identity = biz.get("identity", {})

        # Execute the runner
        raw_result = await cap.runner(identity)
        # Adapt for Firestore/UI consistency
        return cap.response_adapter(raw_result)

    _tool_fn.__name__ = f"run_{cap.name}_analysis"
    _tool_fn.__doc__ = f"Executes a detailed {cap.display_name} for the business."

    return FunctionTool(func=_tool_fn)

def get_all_capability_tools() -> list[FunctionTool]:
    """Returns a list of all enabled capability tools."""
    from backend.workflows.capabilities.registry import get_enabled_capabilities
    tools = []
    for cap in get_enabled_capabilities():
        tool = get_capability_tool(cap.name)
        if tool:
            tools.append(tool)
    return tools
