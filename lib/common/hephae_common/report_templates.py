"""
HTML report generators — 6 templates.
Port of src/lib/reportTemplates.ts.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any, Optional


def _esc(s: Optional[str]) -> str:
    if not s:
        return ""
    return html.escape(str(s), quote=True)


HEPHAE_LOGO_URL = "https://insights.ai.hephae.co/hephae_logo_blue.png"
HEPHAE_APP_URL = "https://hephae.co"

# Default brand color (Hephae blue) — used when business has no discoverable color
_DEFAULT_PRIMARY = "#0052CC"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #hex to (r, g, b). Falls back to Hephae blue on bad input."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return (0, 82, 204)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return (0, 82, 204)


def _resolve_brand(primary: str) -> tuple[str, tuple[int, int, int], str, tuple[int, int, int], str, tuple[int, int, int]]:
    """Derive primary / secondary / accent from a single brand hex.

    Returns (primary_hex, p_rgb, secondary_hex, s_rgb, accent_hex, a_rgb).
    Falls back to Hephae blue when the supplied colour is too light/dark.
    """
    pr, pg, pb = _hex_to_rgb(primary)
    lum = (0.299 * pr + 0.587 * pg + 0.114 * pb) / 255
    if not primary or lum > 0.85 or lum < 0.05:
        primary = _DEFAULT_PRIMARY
        pr, pg, pb = _hex_to_rgb(primary)
    # Secondary: lighter tint of primary
    sr = min(255, int(pr + (255 - pr) * 0.35))
    sg = min(255, int(pg + (255 - pg) * 0.35))
    sb = min(255, int(pb + (255 - pb) * 0.2))
    # Accent: blend primary toward indigo (#6366f1)
    ar = min(255, (pr + 99) // 2)
    ag = min(255, (pg + 102) // 2)
    ab = min(255, (pb + 241) // 2)
    return (
        primary, (pr, pg, pb),
        f"#{sr:02x}{sg:02x}{sb:02x}", (sr, sg, sb),
        f"#{ar:02x}{ag:02x}{ab:02x}", (ar, ag, ab),
    )


def _brand_overrides(primary_color: str) -> str:
    """CSS overrides that re-skin header, blobs, and accents to the business brand."""
    if not primary_color:
        return ""
    p, (pr, pg, pb), s, (sr, sg, sb), a, (ar, ag, ab) = _resolve_brand(primary_color)
    return f"""<style>
  .header {{ background: linear-gradient(135deg, {p} 0%, {s} 50%, {a} 100%); box-shadow: 0 4px 20px rgba({pr},{pg},{pb},0.25); }}
  .blob-1 {{ background: linear-gradient(135deg, rgba({pr},{pg},{pb},0.5), rgba({sr},{sg},{sb},0.4)); }}
  .blob-2 {{ background: linear-gradient(135deg, rgba({ar},{ag},{ab},0.35), rgba({pr},{pg},{pb},0.25)); animation-delay: 2s; }}
  .blob-3 {{ background: linear-gradient(135deg, rgba({sr},{sg},{sb},0.35), rgba({ar},{ag},{ab},0.25)); animation-delay: 4s; }}
  .cta-section {{ background: linear-gradient(135deg, rgba({pr},{pg},{pb},0.06) 0%, rgba({ar},{ag},{ab},0.06) 100%); border-color: rgba({pr},{pg},{pb},0.12); }}
  .cta-secondary {{ color: {p} !important; border-color: rgba({pr},{pg},{pb},0.2); }}
  .cta-secondary:hover {{ border-color: rgba({pr},{pg},{pb},0.4); }}
  a {{ color: {p}; }}
  @media print {{ .header {{ background: {p} !important; }} }}
</style>"""


# Report type → relevant CTA actions (label, emoji, description)
_REPORT_ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    "profile":     [("Margin Surgery", "💰", "margin"), ("Foot Traffic Forecast", "📊", "traffic"), ("SEO Deep Audit", "🔍", "seo"), ("Competitive Analysis", "⚔️", "competitive"), ("Social Media Insights", "📱", "marketing")],
    "margin":      [("Foot Traffic Forecast", "📊", "traffic"), ("SEO Deep Audit", "🔍", "seo"), ("Competitive Analysis", "⚔️", "competitive"), ("Social Media Insights", "📱", "marketing")],
    "traffic":     [("Margin Surgery", "💰", "margin"), ("SEO Deep Audit", "🔍", "seo"), ("Competitive Analysis", "⚔️", "competitive"), ("Social Media Insights", "📱", "marketing")],
    "seo":         [("Margin Surgery", "💰", "margin"), ("Foot Traffic Forecast", "📊", "traffic"), ("Competitive Analysis", "⚔️", "competitive"), ("Social Media Insights", "📱", "marketing")],
    "competitive": [("Margin Surgery", "💰", "margin"), ("Foot Traffic Forecast", "📊", "traffic"), ("SEO Deep Audit", "🔍", "seo"), ("Social Media Insights", "📱", "marketing")],
    "marketing":   [("Margin Surgery", "💰", "margin"), ("Foot Traffic Forecast", "📊", "traffic"), ("SEO Deep Audit", "🔍", "seo"), ("Competitive Analysis", "⚔️", "competitive")],
}


def _shared_styles() -> str:
    return """
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: linear-gradient(-45deg, #f8fafc, #f1f5f9, #f8fafc, #f1f5f9);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        color: #1e293b; line-height: 1.6; min-height: 100vh;
      }
      @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }
      .wrapper { max-width: 800px; margin: 0 auto; padding: 20px 16px 80px; position: relative; z-index: 1; }

      /* ── Glassmorphism & Blobs ── */
      .hephae-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
      .blob { position: absolute; border-radius: 50%; filter: blur(60px); opacity: 0.15; animation: blob 10s infinite; }
      .blob-1 { width: 400px; height: 400px; top: -100px; left: -100px; background: #3b82f6; }
      .blob-2 { width: 300px; height: 300px; bottom: -50px; right: -50px; background: #8b5cf6; animation-delay: 2s; }
      @keyframes blob {
        0% { transform: translate(0,0) scale(1); }
        50% { transform: translate(20px, 40px) scale(1.1); }
        100% { transform: translate(0,0) scale(1); }
      }

      /* ── Header ── */
      .header {
        background: #fff; border: 1px solid rgba(226, 232, 240, 0.8);
        border-radius: 20px; padding: 24px; margin-bottom: 24px;
        display: flex; justify-content: space-between; align-items: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
      }
      .header h1 { font-size: 1.4rem; font-weight: 800; color: #0f172a; }
      .header .subtitle { font-size: 0.85rem; color: #64748b; font-weight: 500; }
      
      /* ── Impact Section ── */
      .impact-hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #fff; border-radius: 24px; padding: 40px 32px; margin-bottom: 24px;
        text-align: center; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.15);
      }
      .impact-value { font-size: 3.5rem; font-weight: 900; line-height: 1; margin: 12px 0; }
      .impact-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; font-weight: 700; }
      .impact-context { font-size: 0.95rem; opacity: 0.85; max-width: 500px; margin: 16px auto 0; line-height: 1.5; }

      /* ── Cards & Sections ── */
      .card {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 20px;
        padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      }
      .card-title { 
        font-size: 0.7rem; font-weight: 800; text-transform: uppercase; 
        letter-spacing: .08em; color: #64748b; margin-bottom: 16px; 
        display: flex; align-items: center; gap: 8px;
      }
      .card-title::after { content: ''; flex: 1; height: 1px; background: #f1f5f9; }

      /* ── Heatmap Tables ── */
      table { width: 100%; border-collapse: separate; border-spacing: 0; }
      th { text-align: left; padding: 12px; font-size: 0.65rem; text-transform: uppercase; color: #94a3b8; border-bottom: 1px solid #f1f5f9; }
      td { padding: 14px 12px; font-size: 0.9rem; border-bottom: 1px solid #f1f5f9; }
      .heat-high { background: rgba(239, 68, 68, 0.05); color: #dc2626; font-weight: 700; }
      .heat-mid { background: rgba(245, 158, 11, 0.05); color: #d97706; font-weight: 600; }
      .heat-low { background: rgba(34, 197, 94, 0.05); color: #16a34a; }

      /* ── Methodology ── */
      .methodology { margin-top: 40px; padding: 20px; border-top: 1px solid #e2e8f0; font-size: 0.75rem; color: #94a3b8; line-height: 1.5; }
      
      /* ── CTAs ── */
      .cta-btn {
        display: inline-flex; align-items: center; justify-content: center;
        padding: 12px 24px; border-radius: 12px; font-weight: 700; font-size: 0.9rem;
        transition: all 0.2s ease; cursor: pointer; text-decoration: none;
      }
      .cta-primary { background: #0f172a; color: #fff !important; }
      .cta-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2); }

      /* ── Mobile ── */
      @media (max-width: 640px) {
        .header { flex-direction: column; text-align: center; gap: 16px; }
        .impact-value { font-size: 2.5rem; }
        .card { padding: 20px; }
        td, th { padding: 10px 8px; font-size: 0.8rem; }
      }
    </style>"""


def _methodology_section(report_type: str) -> str:
    source_map = {
        "margin": "Calculated via Hephae Vision & Margin Engine using local BLS CPI and USDA NASS commodity benchmarks.",
        "seo": "Audited via PageSpeed Insights and Hephae Semantic Crawler against industry-standard SEO core vitals.",
        "traffic": "Forecasted using POI density, local events data, and weather patterns for your specific block.",
        "competitive": "Analyzed via GMB, Yelp, and Official site data across your 2-mile competitive radius.",
        "marketing": "Synthesized from social engagement metrics and neighborhood content trends.",
    }
    method = source_map.get(report_type, "Analyzed using Hephae Multi-Agent Intelligence and local market research.")
    return f"""
    <div class="methodology">
      <strong>Methodology & Data Provenance</strong><br/>
      {method} All findings are benchmarks relative to the median business in your local county.
      This report is an automated diagnostic and should be reviewed with a strategic advisor.
    </div>"""


def _interactive_script(primary_color: str = "") -> str:
    """Inline JS for scroll-reveal, number counters, score bar animation, and parallax."""
    pr, pg, pb = _hex_to_rgb(primary_color) if primary_color else (0, 82, 204)
    return ("""<script>
(function(){
  /* ── Scroll-reveal cards ── */
  var cards = document.querySelectorAll('.card');
  if ('IntersectionObserver' in window) {
    var obs = new IntersectionObserver(function(entries) {
      entries.forEach(function(e, i) {
        if (e.isIntersecting) {
          setTimeout(function(){ e.target.classList.add('visible'); }, i * 80);
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    cards.forEach(function(c){ obs.observe(c); });
  } else {
    cards.forEach(function(c){ c.classList.add('visible'); });
  }

  /* ── Animated number counters ── */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute('data-count'));
    var prefix = el.getAttribute('data-prefix') || '';
    var suffix = el.getAttribute('data-suffix') || '';
    var decimals = (target % 1 !== 0) ? 2 : 0;
    var duration = 1200;
    var start = performance.now();
    function tick(now) {
      var p = Math.min((now - start) / duration, 1);
      var ease = 1 - Math.pow(1 - p, 3);
      var val = (target * ease).toFixed(decimals);
      el.textContent = prefix + (decimals === 0 ? Number(val).toLocaleString() : val) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  var counters = document.querySelectorAll('[data-count]');
  if ('IntersectionObserver' in window) {
    var cobs = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) { animateCount(e.target); cobs.unobserve(e.target); }
      });
    }, { threshold: 0.5 });
    counters.forEach(function(c){ cobs.observe(c); });
  } else {
    counters.forEach(animateCount);
  }

  /* ── Score bar fill animation ── */
  var bars = document.querySelectorAll('.bar-fill');
  bars.forEach(function(b) {
    var w = b.getAttribute('data-width');
    b.style.width = '0%';
    if ('IntersectionObserver' in window) {
      var bobs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
          if (e.isIntersecting) {
            setTimeout(function(){ e.target.style.width = w + '%'; }, 200);
            bobs.unobserve(e.target);
          }
        });
      }, { threshold: 0.3 });
      bobs.observe(b);
    } else {
      b.style.width = w + '%';
    }
  });

  /* ── Score ring animation ── */
  var rings = document.querySelectorAll('.ring-fg');
  rings.forEach(function(r) {
    var circ = parseFloat(r.getAttribute('data-circumference'));
    var pct = parseFloat(r.getAttribute('data-percent'));
    r.style.strokeDasharray = circ;
    r.style.strokeDashoffset = circ;
    if ('IntersectionObserver' in window) {
      var robs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
          if (e.isIntersecting) {
            setTimeout(function(){ e.target.style.strokeDashoffset = circ - (circ * pct / 100); }, 300);
            robs.unobserve(e.target);
          }
        });
      }, { threshold: 0.5 });
      robs.observe(r);
    } else {
      r.style.strokeDashoffset = circ - (circ * pct / 100);
    }
  });

  /* ── Neural particle background ── */
  var canvas = document.getElementById('neuralCanvas');
  if (canvas) {
    var ctx = canvas.getContext('2d');
    var W, H, particles = [], CONN = 140, MOUSE_R = 200;
    var mouse = { x: -1000, y: -1000 };

    function resize() {
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight;
      initParticles();
    }

    function initParticles() {
      particles = [];
      var count = Math.min(Math.floor((W * H) / 12000), 100);
      for (var i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
          size: Math.random() * 2 + 1.2
        });
      }
    }

    function tick() {
      if (!ctx) return;
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        var dx = mouse.x - p.x, dy = mouse.y - p.y;
        var dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < MOUSE_R) {
          var f = (MOUSE_R - dist) / MOUSE_R;
          p.vx -= (dx/dist) * f * 0.04;
          p.vy -= (dy/dist) * f * 0.04;
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
        ctx.fillStyle = 'rgba(0,82,204,0.5)';
        ctx.fill();
        for (var j = i+1; j < particles.length; j++) {
          var dx2 = p.x - particles[j].x, dy2 = p.y - particles[j].y;
          var d = Math.sqrt(dx2*dx2 + dy2*dy2);
          if (d < CONN) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(0,82,204,' + (0.3 - (d/CONN)*0.3).toFixed(3) + ')';
            ctx.lineWidth = 1;
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(tick);
    }

    resize();
    tick();
    window.addEventListener('resize', resize);
    document.addEventListener('mousemove', function(e) { mouse.x = e.clientX; mouse.y = e.clientY; });
    document.addEventListener('mouseleave', function() { mouse.x = -1000; mouse.y = -1000; });
  }
})();
</script>""").replace("0,82,204", f"{pr},{pg},{pb}")


def _score_ring(score: float, color: str, size: int = 100, stroke: int = 8) -> str:
    """Render an SVG circular progress ring with animated fill."""
    r = (size - stroke) / 2
    circ = 2 * 3.14159 * r
    return f"""<div class="score-ring" style="width:{size}px;height:{size}px">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <circle class="ring-bg" cx="{size/2}" cy="{size/2}" r="{r}" stroke-width="{stroke}" />
        <circle class="ring-fg" cx="{size/2}" cy="{size/2}" r="{r}" stroke-width="{stroke}"
          stroke="{color}" data-circumference="{circ:.1f}" data-percent="{score}" />
      </svg>
      <div class="ring-label">
        <span data-count="{score}" style="font-size:{size*0.3}px;font-weight:900;color:{color}">0</span>
        <span style="font-size:{size*0.11}px;opacity:.5;font-weight:400">/100</span>
      </div>
    </div>"""


def _cta_section(report_type: str) -> str:
    """Build the call-to-action section with links to the app and other analyses."""
    actions = _REPORT_ACTIONS.get(report_type, list(_REPORT_ACTIONS.values())[0])
    action_btns = "".join(
        f'<a href="{HEPHAE_APP_URL}" target="_blank" class="cta-btn cta-secondary">{emoji} {label}</a>'
        for label, emoji, _ in actions
    )
    return f"""
    <div class="cta-section card">
      <h3>Unlock more insights for your business</h3>
      <p>Hephae runs AI-powered analyses across every dimension of your business.</p>
      <div class="cta-buttons">
        <a href="{HEPHAE_APP_URL}" target="_blank" class="cta-btn cta-primary">🚀 Try Hephae</a>
        {action_btns}
      </div>
    </div>"""


def _page_wrap(
    title: str,
    business_name: str,
    generated_at: str,
    body: str,
    impact_value: str = "",
    impact_label: str = "",
    impact_context: str = "",
    business_logo_url: str = "",
    report_type: str = "",
    primary_color: str = "",
    favicon_url: str = "",
) -> str:
    # Meta tags for link unfurling
    og_title = f"{title} for {business_name}"
    og_desc = impact_context or f"A comprehensive {title} for {business_name} powered by Hephae AI."
    
    # Render impact hero only if impact_value exists
    hero_html = ""
    if impact_value:
        hero_html = f"""
        <div class="impact-hero">
          <div class="impact-label">{impact_label}</div>
          <div class="impact-value">{impact_value}</div>
          <div class="impact-context">{impact_context}</div>
        </div>"""

    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%B %d, %Y")
    except Exception:
        date_str = generated_at

    # ── Logo with graceful fallback: logo → favicon → initial letter ──
    initial = _esc(business_name[:1].upper()) if business_name else "?"
    fallback_div = f'<div class="biz-logo-fallback" style="display:none">{initial}</div>'
    if business_logo_url:
        onerror_hide = "this.style.display=&apos;none&apos;;this.nextElementSibling.style.display=&apos;flex&apos;"
        if favicon_url:
            onerror = (
                "if(this.dataset.fb){"
                "this.src=this.dataset.fb;delete this.dataset.fb"
                "}else{"
                f"{onerror_hide}"
                "}"
            )
            fb_attr = f' data-fb="{_esc(favicon_url)}"'
        else:
            onerror = onerror_hide
            fb_attr = ""
        biz_logo_html = (
            f'<img src="{_esc(business_logo_url)}" alt="{_esc(business_name)}" '
            f'class="biz-logo" referrerpolicy="no-referrer"{fb_attr} '
            f'onerror="{onerror}" />'
            + fallback_div
        )
    else:
        biz_logo_html = f'<div class="biz-logo-fallback">{initial}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(og_title)}</title>
  <meta property="og:title" content="{_esc(og_title)}" />
  <meta property="og:description" content="{_esc(og_desc)}" />
  <meta property="og:type" content="website" />
  {_shared_styles()}
</head>
<body>
  <div class="hephae-bg"><div class="blob blob-1"></div><div class="blob blob-2"></div></div>
  <div class="wrapper">
    <div class="header">
      <div style="display:flex;align-items:center;gap:14px">
        {biz_logo_html}
        <div>
          <h1>{_esc(business_name)}</h1>
          <div class="subtitle">{_esc(title)}</div>
        </div>
      </div>
      <img src="{HEPHAE_LOGO_URL}" alt="Hephae" style="height:24px;opacity:0.6" />
    </div>
    
    {hero_html}
    {body}
    
    {_methodology_section(report_type)}
    {_cta_section(report_type)}
    
    <div class="footer">
      Powered by Hephae &copy;2026. Data grounded in real-time local research.
    </div>
  </div>
  {_interactive_script(primary_color)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# 1. Profile Report
# ---------------------------------------------------------------------------


def build_profile_report(profile: dict[str, Any]) -> str:
    now = datetime.utcnow().isoformat()

    social_links = profile.get("socialLinks") or {}
    social_rows = "".join(
        f'<tr><td style="opacity:.6;text-transform:capitalize">{_esc(k)}</td>'
        f'<td><a href="{_esc(v)}" target="_blank">{_esc(v)}</a></td></tr>'
        for k, v in social_links.items()
        if v
    )

    competitors = profile.get("competitors") or []
    competitor_rows = "".join(
        f'<tr><td>{_esc(c.get("name"))}</td>'
        f'<td><a href="{_esc(c.get("url"))}" target="_blank">{_esc(c.get("url"))}</a></td>'
        f'<td style="opacity:.7">{_esc(c.get("reason", ""))}</td></tr>'
        for c in competitors
    )

    name = profile.get("name", "")
    body = f"""
      <div class="card">
        <div class="card-title">Business Identity</div>
        <table>
          <tr><td style="opacity:.6;width:140px">Name</td><td><strong>{_esc(name)}</strong></td></tr>
          {"" if not profile.get("address") else f'<tr><td style="opacity:.6">Address</td><td>{_esc(profile.get("address"))}</td></tr>'}
          {"" if not profile.get("officialUrl") else f'<tr><td style="opacity:.6">Website</td><td><a href="{_esc(profile.get("officialUrl"))}" target="_blank">{_esc(profile.get("officialUrl"))}</a></td></tr>'}
          {"" if not profile.get("phone") else f'<tr><td style="opacity:.6">Phone</td><td>{_esc(profile.get("phone"))}</td></tr>'}
          {"" if not profile.get("email") else f'<tr><td style="opacity:.6">Email</td><td>{_esc(profile.get("email"))}</td></tr>'}
          {"" if not profile.get("hours") else f'<tr><td style="opacity:.6">Hours</td><td>{_esc(profile.get("hours"))}</td></tr>'}
          {"" if not profile.get("googleMapsUrl") else f'<tr><td style="opacity:.6">Maps</td><td><a href="{_esc(profile.get("googleMapsUrl"))}" target="_blank">Open in Google Maps</a></td></tr>'}
        </table>
      </div>

      {"" if not social_rows else f'''
      <div class="card">
        <div class="card-title">Social Presence</div>
        <table>{social_rows}</table>
      </div>'''}

      {"" if not competitor_rows else f'''
      <div class="card">
        <div class="card-title">Local Competitors</div>
        <table>
          <thead><tr><th>Name</th><th>URL</th><th>Why Competing</th></tr></thead>
          <tbody>{competitor_rows}</tbody>
        </table>
      </div>'''}
    """

    return _page_wrap(
        "Business Profile", name, now, body,
        business_logo_url=profile.get("logoUrl", ""),
        report_type="profile",
        primary_color=profile.get("primaryColor", ""),
        favicon_url=profile.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 2. Margin Report
# ---------------------------------------------------------------------------


def build_margin_report(report: dict[str, Any], local_context: Optional[dict] = None) -> str:
    menu_items = report.get("menu_items", [])
    total_leakage = sum(i.get("price_leakage", 0) for i in menu_items)
    
    # Impact Headline logic
    county = (local_context or {}).get("county", "your area")
    impact_context = f"We identified a calculated profit gap across {len(menu_items)} menu items relative to the <strong>{county} median</strong>."
    
    rows = ""
    for item in sorted(menu_items, key=lambda x: x.get("price_leakage", 0), reverse=True):
        leak = item.get("price_leakage", 0)
        heat_class = "heat-high" if leak > 2 else "heat-mid" if leak > 0.5 else ""
        rows += f"""<tr class="{heat_class}">
          <td>{_esc(item.get("item_name"))}</td>
          <td>${item.get("current_price", 0):.2f}</td>
          <td style="font-weight:700">${item.get("recommended_price", 0):.2f}</td>
          <td style="font-family:monospace">+${leak:.2f}</td>
        </tr>"""

    body = f"""
      <div class="card">
        <div class="card-title">Profit Leakage Audit</div>
        <table>
          <thead><tr><th>Menu Item</th><th>Current</th><th>Recommended</th><th>Opportunity</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""

    identity = report.get("identity", {})
    return _page_wrap(
        "Margin Surgeon Report", identity.get("name", "Business"),
        report.get("generated_at", datetime.utcnow().isoformat()), body,
        impact_value=f"${total_leakage:,.0f}/mo",
        impact_label="Calculated Monthly Opportunity",
        impact_context=impact_context,
        business_logo_url=identity.get("logoUrl", ""),
        report_type="margin",
        primary_color=identity.get("primaryColor", ""),
        favicon_url=identity.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 3. Traffic Report
# ---------------------------------------------------------------------------


def build_traffic_report(forecast: dict[str, Any]) -> str:
    now = datetime.utcnow().isoformat()

    level_color = {
        "Very High": "#4ade80",
        "High": "#86efac",
        "Medium": "#facc15",
        "Low": "#94a3b8",
        "Closed": "#475569",
    }

    day_cards = ""
    for day in (forecast.get("forecast") or []):
        slot_cells = ""
        for slot in day.get("slots", []):
            bg = level_color.get(slot.get("level", ""), "#94a3b8")
            slot_cells += f"""<td style="text-align:center;padding:10px 6px">
              <div style="font-size:.7rem;opacity:.6;margin-bottom:4px">{_esc(slot.get("label"))}</div>
              <div style="background:{bg};color:#0f172a;font-weight:800;border-radius:8px;padding:6px 4px;font-size:.85rem">{slot.get("score", 0)}</div>
              <div style="font-size:.65rem;opacity:.5;margin-top:3px">{_esc(slot.get("level"))}</div>
            </td>"""

        events = day.get("localEvents") or []
        events_str = " &middot; ".join(_esc(e) for e in events) if events else ""

        day_cards += f"""
        <div class="card" style="margin-bottom:16px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <div>
              <strong style="font-size:1rem">{_esc(day.get("dayOfWeek"))}</strong>
              <span style="opacity:.5;margin-left:8px;font-size:.85rem">{_esc(day.get("date"))}</span>
            </div>
            <span style="font-size:.78rem;opacity:.6">{_esc(day.get("weatherNote"))}</span>
          </div>
          <table style="width:100%"><tr>{slot_cells}</tr></table>
          {"" if not events_str else f'<div style="margin-top:12px;font-size:.78rem;opacity:.6">Events: {events_str}</div>'}
        </div>"""

    business = forecast.get("business") or {}
    pois = (business.get("nearbyPOIs") or [])[:10]
    poi_rows = "".join(
        f'<tr><td>{_esc(p.get("name"))}</td><td style="opacity:.6">{_esc(p.get("type"))}</td></tr>'
        for p in pois
    )

    body = f"""
      <div class="card" style="background:rgba(74,222,128,0.08);border-color:rgba(74,222,128,0.2);margin-bottom:20px">
        <div class="card-title" style="color:#86efac">Executive Summary</div>
        <p style="font-size:.9rem;line-height:1.65">{_esc(forecast.get("summary"))}</p>
      </div>

      <div style="margin-bottom:8px;font-size:.75rem;opacity:.5;text-transform:uppercase;letter-spacing:.08em">3-Day Traffic Forecast</div>
      {day_cards}

      {"" if not poi_rows else f'''
      <div class="card">
        <div class="card-title">Nearby Traffic Anchors</div>
        <table><thead><tr><th>Location</th><th>Type</th></tr></thead><tbody>{poi_rows}</tbody></table>
      </div>'''}
    """

    return _page_wrap(
        "Foot Traffic Forecast",
        business.get("name", "Business"),
        now,
        body,
        business_logo_url=business.get("logoUrl", ""),
        report_type="traffic",
        primary_color=business.get("primaryColor", ""),
        favicon_url=business.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 4. SEO Report
# ---------------------------------------------------------------------------


def _score_bar(score: float) -> str:
    color = "#4ade80" if score >= 80 else "#facc15" if score >= 60 else "#f87171"
    return f"""<div style="display:flex;align-items:center;gap:12px">
      <div style="flex:1;height:8px;background:#e2e8f0;border-radius:999px;overflow:hidden">
        <div class="bar-fill" data-width="{score}" style="height:100%;background:{color};border-radius:999px"></div>
      </div>
      <span data-count="{int(score)}" style="font-weight:800;color:{color};width:36px;text-align:right">0</span>
    </div>"""


def build_seo_report(report: dict[str, Any], identity: Optional[dict[str, Any]] = None, local_context: Optional[dict] = None) -> str:
    now = datetime.utcnow().isoformat()
    score = report.get("overallScore", 0)
    url = report.get("url", "your site")
    
    area = (local_context or {}).get("area", "your neighborhood")
    impact_context = f"Your digital visibility in <strong>{area}</strong> is impacted by key technical performance gaps identified in our neighborhood audit."

    severity_color = {"Critical": "#f87171", "Warning": "#fbbf24", "Info": "#60a5fa"}

    sections_html = ""
    for section in (report.get("sections") or []):
        if not isinstance(section, dict):
            continue
        rec_items = ""
        for rec in (section.get("recommendations") or []):
            if not isinstance(rec, dict):
                continue
            color = severity_color.get(rec.get("severity", ""), "#94a3b8")
            rec_items += f"""<div style="padding:12px 16px;border-left:3px solid {color};background:#f8fafc;border-radius:0 8px 8px 0;margin-bottom:8px">
              <div style="font-size:.72rem;font-weight:700;color:{color};margin-bottom:4px">{_esc(rec.get("severity"))}: {_esc(rec.get("title"))}</div>
              <div style="font-size:.84rem;opacity:.8">{_esc(rec.get("description"))}</div>
            </div>"""

        sections_html += f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <strong>{_esc(section.get("title"))}</strong>
            <span style="font-weight:800;color:#0f172a">{section.get("score", 0)}/100</span>
          </div>
          {"" if not rec_items else f'<div style="margin-top:14px">{rec_items}</div>'}
        </div>"""

    ident = identity or {}
    biz_name = ident.get("name", "") or report.get("url", "Business")
    
    body = f"""
      <div class="card">
        <div class="card-title">Technical Performance Audit</div>
        <div style="font-size:0.9rem;margin-bottom:16px">Analysis of <a href="{_esc(url)}" target="_blank">{_esc(url)}</a></div>
        {sections_html}
      </div>"""

    return _page_wrap(
        "SEO Visibility Audit", biz_name, now, body,
        impact_value=f"{score}/100",
        impact_label="Visibility Health Score",
        impact_context=impact_context,
        business_logo_url=ident.get("logoUrl", ""),
        report_type="seo",
        primary_color=ident.get("primaryColor", ""),
        favicon_url=ident.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 5. Competitive Report
# ---------------------------------------------------------------------------


def build_competitive_report(result: dict[str, Any], identity: dict[str, str]) -> str:
    now = datetime.utcnow().isoformat()

    def threat_color(level: int) -> str:
        return "#f87171" if level >= 8 else "#fbbf24" if level >= 5 else "#4ade80"

    competitor_cards = ""
    for comp in (result.get("competitor_analysis") or []):
        color = threat_color(comp.get("threat_level", 0))
        competitor_cards += f"""
        <div class="card" style="flex:1;min-width:260px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
            <strong style="color:#a5b4fc;font-size:1rem">{_esc(comp.get("name"))}</strong>
            <span style="font-size:.75rem;padding:3px 10px;border-radius:999px;background:{color}22;color:{color};border:1px solid {color}44;font-weight:700">Threat {comp.get("threat_level", "?")}/10</span>
          </div>
          <div style="margin-bottom:10px">
            <div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.07em;opacity:.5;margin-bottom:6px">Key Strength</div>
            <div style="font-size:.84rem;padding:10px;background:rgba(74,222,128,0.07);border:1px solid rgba(74,222,128,0.15);border-radius:8px">{_esc(comp.get("key_strength"))}</div>
          </div>
          <div>
            <div style="font-size:.65rem;text-transform:uppercase;letter-spacing:.07em;opacity:.5;margin-bottom:6px">Exploitable Weakness</div>
            <div style="font-size:.84rem;padding:10px;background:rgba(239,68,68,0.07);border:1px solid rgba(239,68,68,0.15);border-radius:8px">{_esc(comp.get("key_weakness"))}</div>
          </div>
        </div>"""

    advantage_items = "".join(
        f'<li style="padding:12px 16px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.15);border-radius:10px;font-size:.875rem;margin-bottom:8px">{_esc(adv)}</li>'
        for adv in (result.get("strategic_advantages") or [])
    )

    body = f"""
      <div class="card" style="background:rgba(251,146,60,0.08);border-color:rgba(251,146,60,0.2);margin-bottom:20px">
        <div class="card-title" style="color:#fed7aa">Executive Summary</div>
        <p style="font-size:.9rem;line-height:1.65">{_esc(result.get("market_summary"))}</p>
      </div>

      <div style="margin-bottom:8px;font-size:.75rem;opacity:.5;text-transform:uppercase;letter-spacing:.08em">Rival Positioning Radar</div>
      <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:24px">{competitor_cards}</div>

      {"" if not advantage_items else f'''
      <div class="card" style="background:rgba(99,102,241,0.06);border-color:rgba(99,102,241,0.15)">
        <div class="card-title" style="color:#a5b4fc">Strategic Advantages to Leverage</div>
        <ul style="list-style:none">{advantage_items}</ul>
      </div>'''}
    """

    return _page_wrap(
        "Competitive Analysis",
        identity.get("name", "Business"),
        now,
        body,
        business_logo_url=identity.get("logoUrl", ""),
        report_type="competitive",
        primary_color=identity.get("primaryColor", ""),
        favicon_url=identity.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 6. Marketing Report
# ---------------------------------------------------------------------------


def build_marketing_report(result: dict[str, Any], identity: dict[str, Any]) -> str:
    now = datetime.utcnow().isoformat()

    platform = _esc(result.get("platform", "Instagram"))
    creative_raw = result.get("creativeDirection", "")
    draft_raw = result.get("draft", "")

    # Parse creative direction (may be JSON or plain text)
    creative_obj: dict = {}
    if isinstance(creative_raw, str):
        try:
            creative_obj = json.loads(creative_raw)
        except (json.JSONDecodeError, ValueError):
            pass
    elif isinstance(creative_raw, dict):
        creative_obj = creative_raw

    # Creative direction card
    if creative_obj:
        cd_rows = "".join(
            f'<tr><td style="opacity:.6;width:140px;text-transform:capitalize">{_esc(k)}</td>'
            f'<td>{_esc(str(v))}</td></tr>'
            for k, v in creative_obj.items()
        )
        creative_html = f"""
        <div class="card">
          <div class="card-title" style="color:#a78bfa">Creative Direction</div>
          <table>{cd_rows}</table>
        </div>"""
    else:
        creative_html = f"""
        <div class="card">
          <div class="card-title" style="color:#a78bfa">Creative Direction</div>
          <p style="font-size:.9rem;line-height:1.65;white-space:pre-wrap">{_esc(str(creative_raw))}</p>
        </div>"""

    # Draft card
    draft_obj: dict = {}
    if isinstance(draft_raw, str):
        try:
            draft_obj = json.loads(draft_raw)
        except (json.JSONDecodeError, ValueError):
            pass
    elif isinstance(draft_raw, dict):
        draft_obj = draft_raw

    if draft_obj:
        draft_rows = "".join(
            f'<tr><td style="opacity:.6;width:140px;text-transform:capitalize">{_esc(k)}</td>'
            f'<td style="white-space:pre-wrap">{_esc(str(v))}</td></tr>'
            for k, v in draft_obj.items()
        )
        draft_html = f"""
        <div class="card">
          <div class="card-title" style="color:#34d399">Content Draft</div>
          <table>{draft_rows}</table>
        </div>"""
    else:
        draft_html = f"""
        <div class="card">
          <div class="card-title" style="color:#34d399">Content Draft</div>
          <p style="font-size:.9rem;line-height:1.65;white-space:pre-wrap">{_esc(str(draft_raw))}</p>
        </div>"""

    body = f"""
      <div class="card" style="background:rgba(167,139,250,0.08);border-color:rgba(167,139,250,0.2);margin-bottom:20px">
        <div class="card-title" style="color:#c4b5fd">Platform Recommendation</div>
        <div style="font-size:1.4rem;font-weight:800;margin-bottom:8px">{platform}</div>
        <p style="font-size:.85rem;opacity:.7">AI-selected platform based on your business profile, audience, and social presence.</p>
      </div>

      {creative_html}
      {draft_html}
    """

    return _page_wrap(
        "Social Media Insights",
        identity.get("name", "Business"),
        now,
        body,
        business_logo_url=identity.get("logoUrl", ""),
        report_type="marketing",
        primary_color=identity.get("primaryColor", ""),
        favicon_url=identity.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 7. Social Media Audit Report
# ---------------------------------------------------------------------------


def build_social_audit_report(result: dict[str, Any], identity: dict[str, Any]) -> str:
    now = datetime.utcnow().isoformat()
    overall_score = result.get("overall_score", 0)
    summary = _esc(result.get("summary", ""))
    platforms = result.get("platforms", [])
    recs = result.get("strategic_recommendations", [])
    benchmarks = result.get("competitor_benchmarks", [])
    content_strat = result.get("content_strategy", {})
    sources = result.get("sources", [])

    # Score color
    def _score_color(s: int) -> str:
        if s >= 70:
            return "#22c55e"
        if s >= 40:
            return "#eab308"
        return "#ef4444"

    # Overall score card
    score_color = _score_color(overall_score)
    body = f"""
      <div class="card" style="text-align:center;padding:32px 24px">
        <div style="font-size:4rem;font-weight:900;color:{score_color};line-height:1">{overall_score}</div>
        <div style="font-size:.85rem;opacity:.6;text-transform:uppercase;letter-spacing:.1em;margin-top:4px">Overall Social Health Score</div>
        <p style="margin-top:16px;font-size:.95rem;line-height:1.6;max-width:600px;margin-left:auto;margin-right:auto">{summary}</p>
      </div>
    """

    # Per-platform cards
    if platforms:
        platform_cards = ""
        for p in platforms:
            pname = _esc(p.get("name", "unknown")).capitalize()
            pscore = p.get("score", 0)
            pcolor = _score_color(pscore)
            handle = _esc(p.get("handle", ""))
            followers = _esc(str(p.get("followers", "Unknown")))
            freq = _esc(p.get("posting_frequency", "unknown"))
            engagement = _esc(p.get("engagement", "unknown"))
            recency = _esc(p.get("last_post_recency", "Unknown"))
            themes = p.get("content_themes", [])
            strengths = p.get("strengths", [])
            weaknesses = p.get("weaknesses", [])
            precs = p.get("recommendations", [])

            themes_html = " ".join(
                f'<span style="display:inline-block;background:rgba(99,102,241,0.08);color:#6366f1;padding:2px 10px;border-radius:12px;font-size:.75rem;font-weight:600;margin:2px">{_esc(t)}</span>'
                for t in themes[:5]
            )

            strengths_html = "".join(f'<li style="color:#16a34a;font-size:.85rem;margin:4px 0">✓ {_esc(s)}</li>' for s in strengths[:3])
            weaknesses_html = "".join(f'<li style="color:#dc2626;font-size:.85rem;margin:4px 0">✗ {_esc(w)}</li>' for w in weaknesses[:3])
            precs_html = "".join(f'<li style="font-size:.85rem;margin:4px 0;color:#4f46e5">→ {_esc(r)}</li>' for r in precs[:3])

            platform_cards += f"""
            <div class="card" style="margin-bottom:16px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <div>
                  <div class="card-title" style="margin-bottom:2px">{pname}</div>
                  {f'<div style="font-size:.8rem;opacity:.5">{handle}</div>' if handle else ''}
                </div>
                <div style="text-align:center">
                  <div style="font-size:1.8rem;font-weight:800;color:{pcolor};line-height:1">{pscore}</div>
                  <div style="font-size:.65rem;opacity:.5;text-transform:uppercase">/100</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
                <div style="background:rgba(0,0,0,0.02);padding:10px;border-radius:10px;text-align:center">
                  <div style="font-size:.65rem;opacity:.5;text-transform:uppercase;margin-bottom:2px">Followers</div>
                  <div style="font-size:.95rem;font-weight:700">{followers}</div>
                </div>
                <div style="background:rgba(0,0,0,0.02);padding:10px;border-radius:10px;text-align:center">
                  <div style="font-size:.65rem;opacity:.5;text-transform:uppercase;margin-bottom:2px">Posting</div>
                  <div style="font-size:.85rem;font-weight:600">{freq}</div>
                </div>
                <div style="background:rgba(0,0,0,0.02);padding:10px;border-radius:10px;text-align:center">
                  <div style="font-size:.65rem;opacity:.5;text-transform:uppercase;margin-bottom:2px">Engagement</div>
                  <div style="font-size:.85rem;font-weight:600;text-transform:capitalize">{engagement}</div>
                </div>
                <div style="background:rgba(0,0,0,0.02);padding:10px;border-radius:10px;text-align:center">
                  <div style="font-size:.65rem;opacity:.5;text-transform:uppercase;margin-bottom:2px">Last Post</div>
                  <div style="font-size:.85rem;font-weight:600">{recency}</div>
                </div>
              </div>
              {f'<div style="margin-bottom:12px">{themes_html}</div>' if themes_html else ''}
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                {f'<div><div style="font-size:.7rem;font-weight:700;text-transform:uppercase;color:#16a34a;margin-bottom:4px">Strengths</div><ul style="list-style:none;padding:0">{strengths_html}</ul></div>' if strengths_html else ''}
                {f'<div><div style="font-size:.7rem;font-weight:700;text-transform:uppercase;color:#dc2626;margin-bottom:4px">Weaknesses</div><ul style="list-style:none;padding:0">{weaknesses_html}</ul></div>' if weaknesses_html else ''}
              </div>
              {f'<div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(0,0,0,0.06)"><div style="font-size:.7rem;font-weight:700;text-transform:uppercase;color:#4f46e5;margin-bottom:4px">Recommendations</div><ul style="list-style:none;padding:0">{precs_html}</ul></div>' if precs_html else ''}
            </div>"""

        body += f"""
        <div style="margin-top:24px">
          <h2 style="font-size:1.2rem;font-weight:800;margin-bottom:16px">📱 Platform Analysis</h2>
          {platform_cards}
        </div>"""

    # Competitor benchmarks
    if benchmarks:
        bench_rows = ""
        for b in benchmarks:
            bench_rows += f"""
            <tr>
              <td style="padding:10px 12px;font-weight:600">{_esc(b.get('name', ''))}</td>
              <td style="padding:10px 12px;text-transform:capitalize">{_esc(b.get('strongest_platform', ''))}</td>
              <td style="padding:10px 12px">{_esc(str(b.get('followers', 'N/A')))}</td>
              <td style="padding:10px 12px">{_esc(b.get('posting_frequency', 'N/A'))}</td>
              <td style="padding:10px 12px;font-size:.85rem">{_esc(b.get('key_advantage', ''))}</td>
            </tr>"""
        body += f"""
        <div class="card" style="margin-top:24px">
          <h2 style="font-size:1.1rem;font-weight:800;margin-bottom:16px">🏆 Competitor Benchmarks</h2>
          <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-size:.85rem">
              <thead><tr style="border-bottom:2px solid rgba(0,0,0,0.08)">
                <th style="text-align:left;padding:8px 12px;font-size:.7rem;text-transform:uppercase;opacity:.5">Name</th>
                <th style="text-align:left;padding:8px 12px;font-size:.7rem;text-transform:uppercase;opacity:.5">Best Platform</th>
                <th style="text-align:left;padding:8px 12px;font-size:.7rem;text-transform:uppercase;opacity:.5">Followers</th>
                <th style="text-align:left;padding:8px 12px;font-size:.7rem;text-transform:uppercase;opacity:.5">Frequency</th>
                <th style="text-align:left;padding:8px 12px;font-size:.7rem;text-transform:uppercase;opacity:.5">Advantage</th>
              </tr></thead>
              <tbody>{bench_rows}</tbody>
            </table>
          </div>
        </div>"""

    # Strategic recommendations
    if recs:
        rec_items = ""
        for i, r in enumerate(recs, 1):
            impact = r.get("impact", "medium")
            effort = r.get("effort", "medium")
            impact_color = {"high": "#dc2626", "medium": "#eab308", "low": "#22c55e"}.get(impact, "#6b7280")
            effort_color = {"high": "#dc2626", "medium": "#eab308", "low": "#22c55e"}.get(effort, "#6b7280")
            rec_items += f"""
            <div style="display:flex;gap:16px;align-items:flex-start;padding:16px;background:rgba(0,0,0,0.015);border-radius:12px;margin-bottom:8px">
              <div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.85rem;flex-shrink:0">{r.get('priority', i)}</div>
              <div style="flex:1">
                <div style="font-weight:700;margin-bottom:4px">{_esc(r.get('action', ''))}</div>
                <div style="font-size:.8rem;opacity:.7;margin-bottom:6px">{_esc(r.get('rationale', ''))}</div>
                <div style="display:flex;gap:8px">
                  <span style="font-size:.7rem;padding:2px 8px;border-radius:8px;background:rgba({','.join(str(int(impact_color.lstrip('#')[j:j+2], 16)) for j in (0,2,4))},0.1);color:{impact_color};font-weight:600">Impact: {impact}</span>
                  <span style="font-size:.7rem;padding:2px 8px;border-radius:8px;background:rgba({','.join(str(int(effort_color.lstrip('#')[j:j+2], 16)) for j in (0,2,4))},0.1);color:{effort_color};font-weight:600">Effort: {effort}</span>
                </div>
              </div>
            </div>"""
        body += f"""
        <div class="card" style="margin-top:24px">
          <h2 style="font-size:1.1rem;font-weight:800;margin-bottom:16px">🎯 Strategic Recommendations</h2>
          {rec_items}
        </div>"""

    # Content strategy
    if content_strat:
        pillars = content_strat.get("content_pillars", [])
        hashtags = content_strat.get("hashtag_strategy", [])
        schedule = _esc(content_strat.get("posting_schedule", ""))
        quick_wins = content_strat.get("quick_wins", [])

        pillars_html = " ".join(
            f'<span style="display:inline-block;background:rgba(16,185,129,0.08);color:#059669;padding:4px 12px;border-radius:12px;font-size:.8rem;font-weight:600;margin:3px">{_esc(p)}</span>'
            for p in pillars
        )
        hashtags_html = " ".join(
            f'<span style="display:inline-block;background:rgba(99,102,241,0.08);color:#6366f1;padding:4px 12px;border-radius:12px;font-size:.8rem;font-weight:600;margin:3px">{_esc(h)}</span>'
            for h in hashtags[:10]
        )
        qw_html = "".join(f'<li style="font-size:.85rem;margin:6px 0">⚡ {_esc(w)}</li>' for w in quick_wins)

        body += f"""
        <div class="card" style="margin-top:24px">
          <h2 style="font-size:1.1rem;font-weight:800;margin-bottom:16px">📝 Content Strategy</h2>
          {f'<div style="margin-bottom:14px"><div style="font-size:.75rem;font-weight:700;text-transform:uppercase;opacity:.5;margin-bottom:6px">Content Pillars</div>{pillars_html}</div>' if pillars_html else ''}
          {f'<div style="margin-bottom:14px"><div style="font-size:.75rem;font-weight:700;text-transform:uppercase;opacity:.5;margin-bottom:6px">Hashtag Strategy</div>{hashtags_html}</div>' if hashtags_html else ''}
          {f'<div style="margin-bottom:14px"><div style="font-size:.75rem;font-weight:700;text-transform:uppercase;opacity:.5;margin-bottom:6px">Posting Schedule</div><p style="font-size:.9rem">{schedule}</p></div>' if schedule else ''}
          {f'<div><div style="font-size:.75rem;font-weight:700;text-transform:uppercase;opacity:.5;margin-bottom:6px">Quick Wins</div><ul style="list-style:none;padding:0">{qw_html}</ul></div>' if qw_html else ''}
        </div>"""

    # Sources
    if sources:
        src_html = "".join(
            f'<li style="margin:4px 0"><a href="{_esc(s.get("url", ""))}" target="_blank" style="font-size:.85rem">{_esc(s.get("title", s.get("url", "")))}</a></li>'
            for s in sources[:15]
        )
        body += f"""
        <div class="card" style="margin-top:24px;opacity:.8">
          <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;opacity:.5;margin-bottom:8px">Sources</div>
          <ul style="list-style:none;padding:0">{src_html}</ul>
        </div>"""

    return _page_wrap(
        "Social Media Audit",
        identity.get("name", "Business"),
        now,
        body,
        business_logo_url=identity.get("logoUrl", ""),
        report_type="marketing",
        primary_color=identity.get("primaryColor", ""),
        favicon_url=identity.get("favicon", ""),
    )


# ---------------------------------------------------------------------------
# 8. Blog Report
# ---------------------------------------------------------------------------


def build_blog_report(
    article_html: str,
    business_name: str,
    title: str = "",
    hero_image_url: str = "",
    primary_color: str = "",
    logo_url: str = "",
    favicon_url: str = "",
) -> str:
    """Build a full blog post HTML page with the Hephae template wrapper.

    Args:
        article_html: Raw article content HTML (h1, h2, p, blockquote, etc).
        business_name: Name of the business.
        title: Blog post title.
        hero_image_url: URL of the hero/social card image.
        primary_color: Business brand color.
        logo_url: Business logo URL.
        favicon_url: Business favicon URL.
    """
    now = datetime.utcnow().isoformat()

    hero_html = ""
    if hero_image_url:
        hero_html = f"""
      <div class="card" style="padding:0;overflow:hidden;border-radius:16px;margin-bottom:20px">
        <img src="{_esc(hero_image_url)}" alt="{_esc(title)}"
             style="width:100%;height:auto;display:block" />
      </div>"""

    body = f"""
      {hero_html}
      <div class="card">
        <article style="font-size:1rem;line-height:1.8;color:#e2e8f0">
          {article_html}
        </article>
      </div>
    """

    return _page_wrap(
        title or f"Hephae Blog: {business_name}",
        business_name,
        now,
        body,
        business_logo_url=logo_url,
        report_type="profile",
        primary_color=primary_color,
        favicon_url=favicon_url,
    )
