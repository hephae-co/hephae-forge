"""
ProfilerAgent — legacy slow-path business profiler.

Delegates to shared tools (crawl_web_page + screenshot_page) instead of
owning Playwright code directly.  Kept as a thin wrapper so the analyze
slow path still works.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProfilerAgent:
    @staticmethod
    async def profile(url: str) -> dict[str, Any]:
        """
        Profile a business website.
        Extracts colors, logo, persona via crawl_web_page and takes a menu
        screenshot via screenshot_page.

        Returns an EnrichedProfile dict.
        """
        from hephae_agents.shared_tools import crawl_web_page, screenshot_page

        try:
            crawl_result = await crawl_web_page(url, find_menu_link=True)

            menu_screenshot_base64 = None
            menu_url = crawl_result.get("menuUrl")
            if menu_url:
                ss = await screenshot_page(menu_url, quality=80)
                menu_screenshot_base64 = ss.get("screenshot_base64") or None

            return {
                "officialUrl": url,
                "primaryColor": crawl_result.get("primaryColor", "#4f46e5"),
                "secondaryColor": crawl_result.get("secondaryColor", "#ffffff"),
                "logoUrl": crawl_result.get("logoUrl"),
                "persona": crawl_result.get("persona", "Local Business"),
                "menuScreenshotBase64": menu_screenshot_base64,
            }

        except Exception as e:
            logger.error(f"[ProfilerAgent] Failed to profile {url}: {e}")
            return {
                "officialUrl": url,
                "primaryColor": "#4f46e5",
                "secondaryColor": "#ffffff",
                "persona": "Local Business",
            }
