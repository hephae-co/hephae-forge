"""
Visualizer — generates social card PNG using Playwright.
Port of src/agents/margin-analyzer/visualizer.ts.

Returns None if Playwright is not installed (lightweight service mode).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False


async def generate_social_card(
    business_name: str,
    total_leakage: float,
    top_item: str,
) -> bytes | None:
    """
    Generate a branded social card PNG using Playwright.

    Returns None if Playwright is not installed.

    Args:
        business_name: Name of the business.
        total_leakage: Total annual profit leakage amount.
        top_item: Top menu item fix recommendation.

    Returns:
        PNG image as bytes, or None if Playwright unavailable.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        logger.warning("[Visualizer] Playwright not installed — skipping card generation")
        return None

    html = f"""
    <html>
      <body style="width: 600px; height: 400px; margin: 0; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); display: flex; align-items: center; justify-content: center; font-family: sans-serif; color: white;">
        <div style="text-align: center; padding: 40px; border: 4px solid white; border-radius: 20px;">
          <h2 style="margin: 0; font-size: 24px; opacity: 0.9;">HEPHAE INSIGHTS</h2>
          <h1 style="font-size: 48px; margin: 20px 0;">{business_name}</h1>
          <div style="font-size: 64px; font-weight: bold; margin-bottom: 10px;">${total_leakage:,.0f}</div>
          <p style="font-size: 24px; margin: 0;">Potential Annual Profit Recovered</p>
          <div style="margin-top: 30px; padding: 10px 20px; background: rgba(255,255,255,0.2); border-radius: 50px;">
            Top Fix: {top_item}
          </div>
        </div>
      </body>
    </html>
    """

    pw = await async_playwright().__aenter__()
    browser = await pw.chromium.launch()
    try:
        page = await browser.new_page()
        await page.set_viewport_size({"width": 600, "height": 400})
        await page.set_content(html)
        screenshot = await page.screenshot(type="png")
        return screenshot
    finally:
        await browser.close()
