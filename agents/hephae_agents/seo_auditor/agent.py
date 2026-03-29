"""
SeoAuditorAgent — comprehensive SEO auditor across 5 categories.
Port of src/agents/seo-auditor/seoAuditor.ts.
"""

from google.adk.agents import LlmAgent

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.seo_auditor.prompt import SEO_AUDITOR_INSTRUCTION
from hephae_agents.seo_auditor.tools import pagespeed_tool  # noqa: F401
from hephae_agents.shared_tools.google_search import google_search as google_search_tool

seo_auditor_agent = LlmAgent(
    name="seoAuditor",
    description="An elite Technical SEO Auditor capable of analyzing websites using Google Search and PageSpeed Insights.",
    instruction=SEO_AUDITOR_INSTRUCTION,
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    tools=[google_search_tool, pagespeed_tool],
    # output_schema incompatible with tools — Gemini rejects response_schema + tool use
    # Note: ADK built-in google_search cannot be mixed with custom function tools
    # (requires include_server_side_tool_invocations), so we use the shared wrapper instead.
    on_model_error_callback=fallback_on_error,
)
