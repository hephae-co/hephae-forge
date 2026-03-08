"""
SEO auditor tools — PageSpeed Insights (Lighthouse) audit.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)


async def audit_web_performance(url: str) -> dict[str, Any]:
    """
    Run a PageSpeed Insights (Lighthouse) audit on a URL to get quantitative
    performance scores and Core Web Vitals. Call this first for any SEO audit.

    Args:
        url: The full URL to audit (e.g. https://example.com).

    Returns:
        dict with scores, coreWebVitals, topIssues, or error on failure.
    """
    try:
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={quote(url)}&strategy=mobile"
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.get(api_url)

        if res.status_code != 200:
            return {"error": f"PageSpeed API returned {res.status_code}"}

        data = res.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        audits = data.get("lighthouseResult", {}).get("audits", {})

        scores = {
            "performance": round((cats.get("performance", {}).get("score", 0) or 0) * 100),
            "seo": round((cats.get("seo", {}).get("score", 0) or 0) * 100),
            "accessibility": round((cats.get("accessibility", {}).get("score", 0) or 0) * 100),
            "bestPractices": round((cats.get("best-practices", {}).get("score", 0) or 0) * 100),
        }

        core_web_vitals = {
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
            "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
            "fcp": audits.get("first-contentful-paint", {}).get("displayValue"),
            "ttfb": audits.get("server-response-time", {}).get("displayValue"),
            "speedIndex": audits.get("speed-index", {}).get("displayValue"),
            "tbt": audits.get("total-blocking-time", {}).get("displayValue"),
        }

        # Top failing audits (score < 0.9)
        top_issues = sorted(
            [
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "description": (a.get("description", "") or "").split(".")[0],
                    "score": a.get("score"),
                    "displayValue": a.get("displayValue"),
                }
                for a in audits.values()
                if isinstance(a, dict)
                and a.get("score") is not None
                and a.get("score") < 0.9
                and a.get("title")
            ],
            key=lambda x: x.get("score", 1),
        )[:8]

        return {
            "url": url,
            "scores": scores,
            "coreWebVitals": core_web_vitals,
            "topIssues": top_issues,
            "source": "PageSpeed Insights (Lighthouse Mobile)",
        }
    except Exception as e:
        return {"error": f"PageSpeed audit failed: {e}"}


pagespeed_tool = FunctionTool(func=audit_web_performance)
