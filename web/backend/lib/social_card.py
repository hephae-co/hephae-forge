"""
Universal social card generator — creates branded PNG cards for any report type.

Uses Playwright to render HTML → PNG at 1200x630 (Open Graph standard).
Each report type gets a unique gradient and badge.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

HEPHAE_LOGO_URL = "https://insights.ai.hephae.co/hephae_logo_blue.png"

CARD_THEMES: dict[str, dict[str, str]] = {
    "margin": {
        "gradient": "linear-gradient(135deg, #1e3a8a 0%, #4f46e5 100%)",
        "badge": "MARGIN SURGERY",
        "accent": "#818cf8",
    },
    "traffic": {
        "gradient": "linear-gradient(135deg, #92400e 0%, #d97706 100%)",
        "badge": "TRAFFIC FORECAST",
        "accent": "#fbbf24",
    },
    "seo": {
        "gradient": "linear-gradient(135deg, #065f46 0%, #059669 100%)",
        "badge": "SEO AUDIT",
        "accent": "#6ee7b7",
    },
    "competitive": {
        "gradient": "linear-gradient(135deg, #581c87 0%, #7c3aed 100%)",
        "badge": "COMPETITIVE ANALYSIS",
        "accent": "#c4b5fd",
    },
    "marketing": {
        "gradient": "linear-gradient(135deg, #9d174d 0%, #e11d48 100%)",
        "badge": "SOCIAL INSIGHTS",
        "accent": "#fda4af",
    },
    "profile": {
        "gradient": "linear-gradient(135deg, #1e293b 0%, #3b82f6 100%)",
        "badge": "BUSINESS PROFILE",
        "accent": "#93c5fd",
    },
}

DEFAULT_THEME = CARD_THEMES["profile"]


def _build_card_html(
    business_name: str,
    report_type: str,
    headline: str,
    subtitle: str,
    highlight: str = "",
) -> str:
    """Build HTML for a branded social card."""
    theme = CARD_THEMES.get(report_type, DEFAULT_THEME)
    gradient = theme["gradient"]
    badge = theme["badge"]
    accent = theme["accent"]

    highlight_html = ""
    if highlight:
        highlight_html = f"""
        <div style="margin-top: 24px; padding: 10px 24px; background: rgba(255,255,255,0.15);
                    border-radius: 50px; font-size: 18px; font-weight: 500; letter-spacing: 0.3px;
                    backdrop-filter: blur(4px); border: 1px solid rgba(255,255,255,0.2);">
          {highlight}
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      width: 1200px; height: 630px;
      background: {gradient};
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: white;
      display: flex; align-items: center; justify-content: center;
      overflow: hidden;
      position: relative;
    }}
    /* Subtle pattern overlay */
    body::before {{
      content: '';
      position: absolute; inset: 0;
      background: radial-gradient(circle at 20% 80%, rgba(255,255,255,0.05) 0%, transparent 50%),
                  radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 50%);
    }}
    .card {{
      position: relative; z-index: 1;
      width: 1080px; height: 510px;
      border: 2px solid rgba(255,255,255,0.2);
      border-radius: 28px;
      padding: 48px 56px;
      display: flex; flex-direction: column;
      justify-content: space-between;
      background: rgba(255,255,255,0.03);
      backdrop-filter: blur(8px);
    }}
    .top-row {{
      display: flex; align-items: center; justify-content: space-between;
    }}
    .logo-area {{
      display: flex; align-items: center; gap: 12px;
    }}
    .logo-area img {{
      height: 32px; filter: brightness(0) invert(1); opacity: 0.9;
    }}
    .logo-text {{
      font-size: 18px; font-weight: 700; letter-spacing: 2px;
      text-transform: uppercase; opacity: 0.9;
    }}
    .badge {{
      padding: 8px 20px; border-radius: 50px;
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.25);
      font-size: 13px; font-weight: 700; letter-spacing: 1.5px;
      text-transform: uppercase;
    }}
    .center {{
      text-align: center; flex: 1;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
    }}
    .business-name {{
      font-size: 42px; font-weight: 800;
      letter-spacing: -0.5px; margin-bottom: 16px;
      text-shadow: 0 2px 12px rgba(0,0,0,0.15);
    }}
    .headline {{
      font-size: 72px; font-weight: 900;
      letter-spacing: -1px; line-height: 1;
      color: {accent};
      text-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }}
    .subtitle {{
      font-size: 22px; font-weight: 600;
      margin-top: 8px; opacity: 0.85;
      letter-spacing: 0.5px;
    }}
    .bottom {{
      display: flex; align-items: center; justify-content: center;
    }}
    .url {{
      font-size: 16px; font-weight: 600;
      opacity: 0.6; letter-spacing: 1px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="top-row">
      <div class="logo-area">
        <img src="{HEPHAE_LOGO_URL}" alt="Hephae" />
        <span class="logo-text">Hephae</span>
      </div>
      <div class="badge">{badge}</div>
    </div>
    <div class="center">
      <div class="business-name">{business_name}</div>
      <div class="headline">{headline}</div>
      <div class="subtitle">{subtitle}</div>
      {highlight_html}
    </div>
    <div class="bottom">
      <span class="url">hephae.co</span>
    </div>
  </div>
</body>
</html>"""


async def generate_universal_social_card(
    business_name: str,
    report_type: str = "profile",
    headline: str = "",
    subtitle: str = "",
    highlight: str = "",
) -> bytes:
    """Generate a branded social card PNG using Playwright.

    Args:
        business_name: Name of the business.
        report_type: One of margin|traffic|seo|competitive|marketing|profile.
        headline: Big stat or number (e.g., "$847/mo", "85/100").
        subtitle: Supporting text (e.g., "Profit Leakage Detected").
        highlight: Optional callout (e.g., "Top Fix: Lamb Kebab").

    Returns:
        PNG image as bytes (1200x630).
    """
    from playwright.async_api import async_playwright

    html = _build_card_html(business_name, report_type, headline, subtitle, highlight)

    pw = await async_playwright().__aenter__()
    browser = await pw.chromium.launch()
    try:
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1200, "height": 630})
        await page.set_content(html, wait_until="networkidle")
        screenshot = await page.screenshot(type="png")
        return screenshot
    finally:
        await browser.close()
