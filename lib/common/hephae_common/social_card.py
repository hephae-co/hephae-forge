"""Universal social card generator — creates branded PNG cards for any report type.

Uses Playwright to render HTML -> PNG at 1200x630 (Open Graph standard).
When Playwright is not installed, returns None (graceful degradation).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

HEPHAE_LOGO_URL = "https://insights.ai.hephae.co/hephae_logo_blue.png"

CARD_THEMES: dict[str, dict[str, str]] = {
    "margin": {"gradient": "linear-gradient(135deg, #1e3a8a 0%, #4f46e5 100%)", "badge": "MARGIN SURGERY", "accent": "#818cf8"},
    "traffic": {"gradient": "linear-gradient(135deg, #92400e 0%, #d97706 100%)", "badge": "TRAFFIC FORECAST", "accent": "#fbbf24"},
    "seo": {"gradient": "linear-gradient(135deg, #065f46 0%, #059669 100%)", "badge": "SEO AUDIT", "accent": "#6ee7b7"},
    "competitive": {"gradient": "linear-gradient(135deg, #581c87 0%, #7c3aed 100%)", "badge": "COMPETITIVE ANALYSIS", "accent": "#c4b5fd"},
    "marketing": {"gradient": "linear-gradient(135deg, #9d174d 0%, #e11d48 100%)", "badge": "SOCIAL INSIGHTS", "accent": "#fda4af"},
    "profile": {"gradient": "linear-gradient(135deg, #1e293b 0%, #3b82f6 100%)", "badge": "BUSINESS PROFILE", "accent": "#93c5fd"},
}

DEFAULT_THEME = CARD_THEMES["profile"]


def _build_card_html(
    business_name: str, report_type: str, headline: str, subtitle: str, highlight: str = "",
    stat_pills: list[str] | None = None,
) -> str:
    """Build an OG image card HTML.

    Args:
        stat_pills: Up to 4 short strings shown as pill badges below the subtitle,
                    e.g. ["35.9% food cost", "399 items", "6 restaurants"].
                    When provided they replace the generic highlight pill.
    """
    theme = CARD_THEMES.get(report_type, DEFAULT_THEME)
    gradient = theme["gradient"]
    badge = theme["badge"]
    accent = theme["accent"]

    # Build pills row — prefer stat_pills over legacy highlight string
    pills_html = ""
    pills = stat_pills or ([highlight] if highlight else [])
    if pills:
        pill_items = "".join(
            f'<span style="padding:8px 20px;background:rgba(255,255,255,0.15);border-radius:50px;'
            f'font-size:15px;font-weight:600;letter-spacing:0.2px;border:1px solid rgba(255,255,255,0.25);'
            f'white-space:nowrap">{p}</span>'
            for p in pills[:4]
        )
        pills_html = f'<div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:22px">{pill_items}</div>'

    # Decorative bar chart (last 4 values as relative-height bars) if headline is numeric-looking
    import re as _re
    bars_html = ""
    m = _re.match(r"^(\d+(?:\.\d+)?)", headline.strip())
    if m and stat_pills and len(stat_pills) >= 3:
        # Extract first number from each pill for a mini bar visual
        nums = []
        for p in stat_pills[:4]:
            nm = _re.search(r"(\d+(?:\.\d+)?)", p)
            if nm:
                nums.append(float(nm.group(1)))
        if len(nums) >= 3:
            maxv = max(nums) or 1
            bar_items = "".join(
                f'<div style="width:28px;background:{accent};opacity:{0.5 + 0.5*v/maxv:.2f};'
                f'border-radius:4px 4px 0 0;height:{int(60*v/maxv)+8}px;margin:0 4px;align-self:flex-end"></div>'
                for v in nums
            )
            bars_html = (
                f'<div style="position:absolute;bottom:48px;right:56px;display:flex;align-items:flex-end;'
                f'opacity:0.6">{bar_items}</div>'
            )

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
      overflow: hidden; position: relative;
    }}
    body::before {{
      content: '';
      position: absolute; inset: 0;
      background: radial-gradient(circle at 15% 85%, rgba(255,255,255,0.06) 0%, transparent 50%),
                  radial-gradient(circle at 85% 15%, rgba(255,255,255,0.09) 0%, transparent 45%),
                  radial-gradient(circle at 50% 50%, rgba(0,0,0,0.08) 0%, transparent 70%);
    }}
    /* Diagonal stripe texture */
    body::after {{
      content: '';
      position: absolute; inset: 0;
      background-image: repeating-linear-gradient(
        45deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 1px,
        transparent 1px, transparent 28px
      );
    }}
    .card {{
      position: relative; z-index: 1;
      width: 1100px; height: 540px;
      border: 1.5px solid rgba(255,255,255,0.18); border-radius: 28px;
      padding: 44px 60px;
      display: flex; flex-direction: column; justify-content: space-between;
      background: rgba(255,255,255,0.04); backdrop-filter: blur(6px);
    }}
    .top-row {{ display: flex; align-items: center; justify-content: space-between; }}
    .logo-area {{ display: flex; align-items: center; gap: 14px; }}
    .logo-area img {{ height: 30px; filter: brightness(0) invert(1); opacity: 0.85; }}
    .logo-text {{ font-size: 17px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; opacity: 0.85; }}
    .badge {{
      padding: 7px 18px; border-radius: 50px;
      background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.22);
      font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; opacity: 0.9;
    }}
    .center {{ flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 12px 0; }}
    .eyebrow {{ font-size: 13px; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase; opacity: 0.65; margin-bottom: 12px; }}
    .headline-stat {{ font-size: 80px; font-weight: 900; letter-spacing: -2px; line-height: 1; color: {accent}; text-shadow: 0 4px 24px rgba(0,0,0,0.25); }}
    .headline-text {{ font-size: 34px; font-weight: 800; line-height: 1.2; letter-spacing: -0.5px; margin-top: 10px; max-width: 800px; }}
    .subtitle {{ font-size: 18px; font-weight: 500; margin-top: 10px; opacity: 0.75; }}
    .bottom {{ display: flex; align-items: center; justify-content: space-between; }}
    .url {{ font-size: 14px; font-weight: 600; opacity: 0.5; letter-spacing: 1.5px; text-transform: lowercase; }}
    .powered {{ font-size: 12px; opacity: 0.45; letter-spacing: 0.5px; }}
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
      <div class="eyebrow">{business_name}</div>
      <div class="headline-stat">{headline}</div>
      <div class="headline-text">{subtitle}</div>
      {pills_html}
    </div>
    <div class="bottom">
      <span class="url">hephae.co</span>
      <span class="powered">Powered by Hephae Intelligence</span>
    </div>
    {bars_html}
  </div>
</body>
</html>"""


async def generate_universal_social_card(
    business_name: str, report_type: str = "profile",
    headline: str = "", subtitle: str = "", highlight: str = "",
    stat_pills: list[str] | None = None,
) -> bytes | None:
    """Generate a branded social card PNG using Playwright.

    Args:
        stat_pills: Up to 4 short data strings shown as pill badges, e.g.
                    ["35.9% food cost", "399 items", "6 restaurants"].
                    Replaces the generic `highlight` pill when provided.

    Returns None if Playwright is not installed (lightweight service mode).
    """
    if not _PLAYWRIGHT_AVAILABLE:
        logger.warning("[SocialCard] Playwright not installed — skipping card generation")
        return None

    html = _build_card_html(business_name, report_type, headline, subtitle, highlight, stat_pills=stat_pills)

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
