"""
SeoAuditorAgent — comprehensive SEO auditor across 5 categories.
Port of src/agents/seo-auditor/seoAuditor.ts.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.load_memory_tool import load_memory_tool

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_capabilities.shared_tools import google_search_tool
from hephae_capabilities.seo_auditor.prompt import SEO_AUDITOR_INSTRUCTION
from hephae_capabilities.seo_auditor.tools import pagespeed_tool  # noqa: F401
seo_auditor_agent = LlmAgent(
    name="seoAuditor",
    description="An elite Technical SEO Auditor capable of analyzing websites using Google Search and PageSpeed Insights.",
    instruction=SEO_AUDITOR_INSTRUCTION,
    model=AgentModels.ENHANCED_MODEL,
    tools=[google_search_tool, pagespeed_tool, load_memory_tool],
    # output_schema incompatible with tools — Gemini rejects response_schema + tool use
    on_model_error_callback=fallback_on_error,
)
