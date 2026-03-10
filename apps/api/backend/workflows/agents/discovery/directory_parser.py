"""
DirectoryParserAgent — extracts structured business lists from raw crawl data.

Handles various directory layouts (tables, lists, cards) found on 
Chamber of Commerce or Municipal websites.
"""

from __future__ import annotations

import logging
from google.adk.agents import LlmAgent
from backend.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import ZipcodeScannerOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

PARSER_INSTRUCTION = """You are a Data Extraction Specialist.
Your job is to extract a list of local businesses from the provided raw website content.

The content comes from a Chamber of Commerce or Municipal directory.
Extract ONLY the businesses that match the requested CATEGORY. 
If no category is provided, extract all relevant local businesses.

RULES:
1. Exclude national chains/franchises.
2. Clean up names (e.g., remove "Inc.", "LLC" if it clutters the name).
3. Ensure addresses are complete.
4. If a website is missing but you see a "View Profile" link, use that as the placeholder.

Return a JSON object with a 'businesses' array:
{
  "businesses": [
    { "name": "Name", "address": "Full Address", "website": "URL", "category": "Category" }
  ]
}"""

DirectoryParserAgent = LlmAgent(
    name="directory_parser",
    model=AgentModels.PRIMARY_MODEL,
    instruction=PARSER_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)

async def parse_directory_content(content: str, category: str | None = None) -> list[dict]:
    """Parse raw HTML/Markdown into a list of business dicts."""
    prompt = f"CATEGORY FILTER: {category or 'All Local Businesses'}\n\nCONTENT:\n{content[:30000]}"
    
    result = await run_agent_to_json(
        DirectoryParserAgent, 
        prompt, 
        app_name="directory_parser",
        response_schema=ZipcodeScannerOutput
    )
    
    if result and isinstance(result, ZipcodeScannerOutput):
        return [b.model_dump() for b in result.businesses]
    return []
