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


# Hephae brand colors
COLORS = [
    "#d97706",  # amber (primary)
    "#475569",  # slate
    "#059669",  # emerald
    "#7c3aed",  # violet
    "#dc2626",  # red
    "#0284c7",  # sky
    "#ca8a04",  # yellow
    "#6366f1",  # indigo
]


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
) -> str:
    """Generate a Chart.js chart as an HTML block (canvas + script).

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

    Returns:
        HTML string with <div>, <canvas>, and <script> tags.
    """
    is_horizontal = chart_type == "horizontalBar"
    actual_type = "bar" if is_horizontal else chart_type

    colors = COLORS[: len(values)]
    border_colors = colors

    datasets = [
        {
            "label": dataset_label or title,
            "data": values,
            "backgroundColor": colors if chart_type in ("pie", "doughnut", "bar", "horizontalBar") else [COLORS[0]],
            "borderColor": border_colors if chart_type in ("pie", "doughnut") else [COLORS[0]],
            "borderWidth": 1,
        }
    ]

    if secondary_values:
        datasets.append(
            {
                "label": secondary_label,
                "data": secondary_values,
                "backgroundColor": [COLORS[1]],
                "borderColor": [COLORS[1]],
                "borderWidth": 1,
            }
        )

    options: dict[str, Any] = {
        "responsive": True,
        "maintainAspectRatio": True,
        "plugins": {
            "title": {"display": True, "text": title, "font": {"size": 16}},
            "legend": {"display": bool(secondary_values) or chart_type in ("pie", "doughnut")},
        },
    }

    if is_horizontal:
        options["indexAxis"] = "y"

    chart_config = json.dumps(
        {"type": actual_type, "data": {"labels": labels, "datasets": datasets}, "options": options}
    )

    # Accessibility: text fallback for screen readers
    fallback_rows = "\n".join(f"    <li>{l}: {v}</li>" for l, v in zip(labels, values))

    return f"""<div class="chart-container" style="max-width:700px;margin:2rem auto">
  <canvas id="{chart_id}" width="700" height="400" role="img" aria-label="{html_lib.escape(title)}"></canvas>
  <noscript>
    <ul>
{fallback_rows}
    </ul>
  </noscript>
  {f'<p class="chart-caption" style="text-align:center;color:#6b7280;font-size:0.9rem;margin-top:0.5rem">{html_lib.escape(caption)}</p>' if caption else ''}
  <script>
    new Chart(document.getElementById('{chart_id}'), {chart_config});
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
