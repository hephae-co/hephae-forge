"""
Shared Gemini-grounded Google Search tool.

Uses Gemini's built-in `googleSearch` grounding to execute real web searches.
Port of src/agents/tools/googleSearchTool.ts.
"""

from __future__ import annotations

import logging
import os

from google import genai
from google.genai import types

from backend.config import AgentModels

logger = logging.getLogger(__name__)


async def google_search(query: str) -> dict:
    """
    Search Google for a query to find factual information, URLs, or real-world entities.
    Uses Gemini's built-in googleSearch grounding.

    Args:
        query: The search query to execute.

    Returns:
        dict with 'result' (summarized text) and 'sources' (list of source URLs), or 'error' on failure.
    """
    try:
        logger.info(f"[GoogleSearchTool] Executing grounded query: {query}")
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        response = await client.aio.models.generate_content(
            model=AgentModels.DEFAULT_FAST_MODEL,
            contents=(
                f"Search for: {query}\n\n"
                "List ALL relevant URLs found in the search results with their full URLs. "
                "Be precise with URLs — do not invent or modify them."
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        # Extract source URLs from grounding metadata
        sources: list[dict[str, str]] = []
        try:
            candidate = response.candidates[0] if response.candidates else None
            gm = getattr(candidate, "grounding_metadata", None) if candidate else None
            if gm and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    if chunk.web and chunk.web.uri:
                        sources.append({
                            "url": chunk.web.uri,
                            "title": chunk.web.title or "",
                        })
        except Exception:
            pass  # Grounding metadata extraction is best-effort

        return {"result": response.text, "sources": sources}
    except Exception as e:
        logger.error(f"[GoogleSearchTool] Failed: {e}")
        return {"error": "Search failed."}
