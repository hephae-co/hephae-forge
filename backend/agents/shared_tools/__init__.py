"""
Shared tools used by 3+ agent groups.

Re-exports raw functions and pre-wrapped FunctionTool instances so agent
modules can do:

    from backend.agents.shared_tools import google_search_tool, playwright_tool, crawl4ai_tool
"""

from google.adk.tools import FunctionTool

from backend.agents.shared_tools.google_search import google_search
from backend.agents.shared_tools.playwright import crawl_web_page
from backend.agents.shared_tools.crawl4ai import (
    crawl_for_content,
    crawl_with_options,
    crawl_multiple_pages,
)
from backend.agents.shared_tools.validate_url import validate_url

google_search_tool = FunctionTool(func=google_search)
playwright_tool = FunctionTool(func=crawl_web_page)
crawl4ai_tool = FunctionTool(func=crawl_for_content)
crawl4ai_advanced_tool = FunctionTool(func=crawl_with_options)
crawl4ai_deep_tool = FunctionTool(func=crawl_multiple_pages)
validate_url_tool = FunctionTool(func=validate_url)
