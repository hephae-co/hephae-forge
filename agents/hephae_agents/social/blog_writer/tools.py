"""Blog writer tools — deterministic HTML generators for charts, SEO, and social sharing.

These are FunctionTools used by blog agents. They take structured input
and return HTML strings — no LLM involved.
"""

from __future__ import annotations

import json
import html as html_lib
import urllib.parse
from datetime import datetime
from typing import Any


# Hephae brand palette — semantic color sets
_PALETTE_DANGER  = ["#ef4444", "#f97316", "#eab308", "#f43f5e", "#fb7185", "#fca5a5", "#fed7aa", "#fef08a"]
_PALETTE_BRAND   = ["#d97706", "#f59e0b", "#fbbf24", "#fcd34d", "#b45309", "#92400e", "#78350f", "#451a03"]
_PALETTE_COOL    = ["#3b82f6", "#6366f1", "#8b5cf6", "#0ea5e9", "#06b6d4", "#14b8a6", "#10b981", "#22c55e"]
_PALETTE_MIXED   = ["#d97706", "#059669", "#3b82f6", "#7c3aed", "#ef4444", "#0284c7", "#ca8a04", "#6366f1"]

# Colour theme selector — pick a themed palette based on a hint keyword
_THEME_MAP: dict[str, list[str]] = {
    "danger": _PALETTE_DANGER,
    "cost":   _PALETTE_DANGER,
    "risk":   _PALETTE_DANGER,
    "warn":   _PALETTE_BRAND,
    "brand":  _PALETTE_BRAND,
    "cool":   _PALETTE_COOL,
    "growth": _PALETTE_COOL,
    "mixed":  _PALETTE_MIXED,
}


def _pick_colors(n: int, theme: str = "mixed") -> list[str]:
    palette = _THEME_MAP.get(theme.lower(), _PALETTE_MIXED)
    return (palette * ((n // len(palette)) + 1))[:n]


def generate_chart_js(
    chart_id: str,
    chart_type: str,
    title: str,
    labels: list[str],
    values: list[float],
    caption: str = "",
    dataset_label: str = "",
    secondary_values: list[float] | None = None,
    secondary_label: str = "",
    color_theme: str = "mixed",
    reference_line: float | None = None,
    reference_label: str = "",
) -> str:
    """Generate a richly styled Chart.js chart as an HTML block.

    Args:
        chart_id: Unique DOM id for the canvas element.
        chart_type: "bar", "line", "pie", "doughnut", "radar", or "horizontalBar".
        title: Chart title displayed above the chart.
        labels: X-axis labels (or category labels for pie/doughnut).
        values: Primary data values.
        caption: Insight caption displayed below the chart.
        dataset_label: Label for the primary dataset.
        secondary_values: Optional second dataset for grouped bar/line.
        secondary_label: Label for the secondary dataset.
        color_theme: "danger" (reds/oranges), "cool" (blues/greens), "brand" (ambers), "mixed".
        reference_line: Draw a horizontal/vertical annotation line at this value.
        reference_label: Label for the reference line.

    Returns:
        HTML string with <div>, <canvas>, and <script> tags.
    """
    is_horizontal = chart_type == "horizontalBar"
    actual_type = "bar" if is_horizontal else chart_type
    is_circular = chart_type in ("pie", "doughnut")

    colors = _pick_colors(len(values), color_theme)

    # Gradient fill helper (injected via inline JS for line charts)
    use_gradient = actual_type == "line"

    if is_circular:
        bg_colors = colors
        border_colors = ["#ffffff"] * len(values)
        border_width = 3
    elif use_gradient:
        # Will be replaced by JS gradient at render time
        bg_colors = [f"{colors[0]}33"]  # translucent fill
        border_colors = [colors[0]]
        border_width = 3
    else:
        bg_colors = colors
        border_colors = [c + "cc" for c in colors]
        border_width = 0

    datasets: list[dict[str, Any]] = [
        {
            "label": dataset_label or title,
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": border_width,
            "borderRadius": 6 if actual_type == "bar" else 0,
            "borderSkipped": False,
            "tension": 0.4 if use_gradient else 0,
            "fill": use_gradient,
            "pointBackgroundColor": colors[0] if use_gradient else None,
            "pointRadius": 5 if use_gradient else None,
            "pointHoverRadius": 8 if use_gradient else None,
        }
    ]

    if secondary_values:
        sec_color = _pick_colors(1, "cool")[0]
        datasets.append({
            "label": secondary_label,
            "data": secondary_values,
            "backgroundColor": sec_color + "99",
            "borderColor": sec_color,
            "borderWidth": border_width,
            "borderRadius": 6 if actual_type == "bar" else 0,
            "borderSkipped": False,
        })

    options: dict[str, Any] = {
        "responsive": True,
        "maintainAspectRatio": True,
        "animation": {"duration": 900, "easing": "easeOutQuart"},
        "plugins": {
            "title": {
                "display": True,
                "text": title,
                "font": {"size": 17, "weight": "700", "family": "'Inter', sans-serif"},
                "color": "#111827",
                "padding": {"bottom": 16},
            },
            "legend": {
                "display": bool(secondary_values) or is_circular,
                "labels": {"font": {"size": 13}, "padding": 16, "usePointStyle": True},
            },
            "tooltip": {
                "backgroundColor": "#1f2937",
                "titleFont": {"size": 13, "weight": "600"},
                "bodyFont": {"size": 12},
                "padding": 12,
                "cornerRadius": 8,
                "displayColors": True,
            },
        },
        "scales": {} if is_circular else {
            "x": {
                "grid": {"display": False},
                "ticks": {"font": {"size": 12}, "color": "#6b7280"},
            },
            "y": {
                "grid": {"color": "#f3f4f6", "drawBorder": False},
                "ticks": {"font": {"size": 12}, "color": "#6b7280"},
                "beginAtZero": True,
            },
        },
    }

    if is_horizontal:
        options["indexAxis"] = "y"
        # Swap scale keys for horizontal
        options["scales"] = {
            "x": {"grid": {"color": "#f3f4f6"}, "ticks": {"font": {"size": 12}, "color": "#6b7280"}, "beginAtZero": True},
            "y": {"grid": {"display": False}, "ticks": {"font": {"size": 12}, "color": "#374151"}, "crossAlign": "far"},
        }

    if is_circular:
        options["plugins"]["legend"]["position"] = "bottom"  # type: ignore[index]

    chart_data = {"labels": labels, "datasets": datasets}
    chart_config_str = json.dumps({"type": actual_type, "data": chart_data, "options": options})

    # Reference line annotation (drawn via afterDraw plugin — no extra CDN needed)
    ref_js = ""
    if reference_line is not None and not is_circular:
        axis = "x" if is_horizontal else "y"
        ref_js = f"""
    // Reference line annotation
    Chart.register({{
      id: 'refLine_{chart_id}',
      afterDraw(chart) {{
        const ctx = chart.ctx;
        const {axis}Scale = chart.scales['{axis}'];
        const pos = {axis}Scale.getPixelForValue({reference_line});
        ctx.save();
        ctx.beginPath();
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        {'ctx.moveTo(chart.chartArea.left, pos); ctx.lineTo(chart.chartArea.right, pos);' if axis == 'y' else 'ctx.moveTo(pos, chart.chartArea.top); ctx.lineTo(pos, chart.chartArea.bottom);'}
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 11px Inter, sans-serif';
        ctx.fillText('{html_lib.escape(reference_label or str(reference_line))}', chart.chartArea.left + 4, pos - 5);
        ctx.restore();
      }}
    }});"""

    # Accessibility: text fallback for screen readers
    fallback_rows = "\n".join(f"    <li>{lbl}: {val}</li>" for lbl, val in zip(labels, values))

    caption_html = (
        f'<p style="text-align:center;color:#6b7280;font-size:0.875rem;margin-top:0.75rem;font-style:italic">'
        f'{html_lib.escape(caption)}</p>'
        if caption else ""
    )

    return f"""<div class="hephae-chart" style="max-width:720px;margin:2.5rem auto;background:#ffffff;border-radius:16px;padding:1.75rem 2rem;box-shadow:0 1px 3px rgba(0,0,0,0.06),0 4px 16px rgba(0,0,0,0.04);border:1px solid #f3f4f6">
  <canvas id="{chart_id}" role="img" aria-label="{html_lib.escape(title)}" style="max-height:380px"></canvas>
  <noscript><ul aria-label="{html_lib.escape(title)}">{fallback_rows}</ul></noscript>
  {caption_html}
  <script>
    (function() {{
      {ref_js}
      var cfg = {chart_config_str};
      new Chart(document.getElementById('{chart_id}'), cfg);
    }})();
  </script>
</div>"""


def inject_seo_meta(
    title: str,
    description: str,
    keywords: list[str],
    canonical_url: str,
    og_image_url: str = "",
    author: str = "Hephae Intelligence",
    published_date: str = "",
) -> str:
    """Generate SEO meta tags for a blog post.

    Returns an HTML string to be inserted inside <head>.
    """
    if not published_date:
        published_date = datetime.utcnow().strftime("%Y-%m-%d")

    esc = html_lib.escape
    tags = [
        f'<title>{esc(title)} | Hephae</title>',
        f'<meta name="description" content="{esc(description[:160])}">',
        f'<meta name="keywords" content="{esc(", ".join(keywords))}">',
        f'<meta name="author" content="{esc(author)}">',
        f'<link rel="canonical" href="{esc(canonical_url)}">',
        # Open Graph
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description[:200])}">',
        f'<meta property="og:type" content="article">',
        f'<meta property="og:url" content="{esc(canonical_url)}">',
        f'<meta property="article:published_time" content="{published_date}">',
        f'<meta property="article:author" content="{esc(author)}">',
        # Twitter Card
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(description[:200])}">',
    ]

    if og_image_url:
        tags.append(f'<meta property="og:image" content="{esc(og_image_url)}">')
        tags.append(f'<meta name="twitter:image" content="{esc(og_image_url)}">')

    return "\n    ".join(tags)


def inject_social_share(title: str, url: str) -> str:
    """Generate social sharing buttons HTML block."""
    enc_title = urllib.parse.quote(title)
    enc_url = urllib.parse.quote(url)

    return f"""<div class="social-share" style="margin:2rem 0;padding:1rem 0;border-top:1px solid #e5e7eb;text-align:center">
  <p style="color:#6b7280;margin-bottom:0.75rem;font-size:0.9rem">Share this analysis:</p>
  <a href="https://twitter.com/intent/tweet?text={enc_title}&url={enc_url}" target="_blank" rel="noopener"
     style="display:inline-block;padding:0.5rem 1rem;margin:0 0.25rem;background:#1DA1F2;color:white;border-radius:6px;text-decoration:none;font-size:0.85rem">Twitter/X</a>
  <a href="https://www.linkedin.com/sharing/share-offsite/?url={enc_url}" target="_blank" rel="noopener"
     style="display:inline-block;padding:0.5rem 1rem;margin:0 0.25rem;background:#0A66C2;color:white;border-radius:6px;text-decoration:none;font-size:0.85rem">LinkedIn</a>
  <a href="https://www.facebook.com/sharer/sharer.php?u={enc_url}" target="_blank" rel="noopener"
     style="display:inline-block;padding:0.5rem 1rem;margin:0 0.25rem;background:#1877F2;color:white;border-radius:6px;text-decoration:none;font-size:0.85rem">Facebook</a>
</div>"""


def inject_schema_org(
    title: str,
    description: str,
    url: str,
    image_url: str = "",
    published_date: str = "",
    word_count: int = 0,
) -> str:
    """Generate Schema.org JSON-LD for a BlogPosting."""
    if not published_date:
        published_date = datetime.utcnow().isoformat() + "Z"

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": description[:200],
        "url": url,
        "datePublished": published_date,
        "author": {"@type": "Organization", "name": "Hephae Intelligence", "url": "https://hephae.co"},
        "publisher": {"@type": "Organization", "name": "Hephae", "url": "https://hephae.co"},
    }
    if image_url:
        schema["image"] = image_url
    if word_count:
        schema["wordCount"] = word_count

    return f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'


def generate_chartjs_library_tag() -> str:
    """Return the Chart.js CDN script tag. Include once in the page <head> or before charts."""
    return '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>'
