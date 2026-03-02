"""
Minimal crawl4ai REST server for integration tests.

Mirrors the Docker container's /crawl and /health endpoints using
the crawl4ai library directly. Run with:
    python -m backend.tests.integration._crawl4ai_server
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Lazy-init the crawler so we only create one browser
_crawler = None
_lock = asyncio.Lock()


async def _get_crawler():
    global _crawler
    if _crawler is None:
        async with _lock:
            if _crawler is None:
                from crawl4ai import AsyncWebCrawler
                _crawler = AsyncWebCrawler()
                await _crawler.__aenter__()
                logger.info("Crawler initialized")
    return _crawler


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/crawl")
async def crawl(request: Request):
    body = await request.json()
    urls = body.get("urls", [])
    if not urls:
        return JSONResponse({"error": "No URLs provided"}, status_code=400)

    crawler_config = body.get("crawler_config", {})
    params = crawler_config.get("params", {})

    from crawl4ai import CrawlerRunConfig

    deep_crawl_spec = params.pop("deep_crawl", None)

    # Build CrawlerRunConfig from params
    config_kwargs = {}
    if params.get("js_code"):
        config_kwargs["js_code"] = params["js_code"]
    if params.get("wait_for"):
        config_kwargs["wait_for"] = params["wait_for"]
    if params.get("css_selector"):
        config_kwargs["css_selector"] = params["css_selector"]
    if params.get("scan_full_page"):
        config_kwargs["scan_full_page"] = True
    if params.get("process_iframes"):
        config_kwargs["process_iframes"] = True
    if params.get("remove_overlay_elements"):
        config_kwargs["remove_overlay_elements"] = True
    if params.get("page_timeout"):
        config_kwargs["page_timeout"] = params["page_timeout"]

    # Handle deep crawl
    if deep_crawl_spec:
        from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
        from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

        dp = deep_crawl_spec.get("params", {})
        strategy_kwargs = {
            "max_depth": dp.get("max_depth", 2),
            "max_pages": dp.get("max_pages", 10),
        }

        # Handle filter_pattern
        filter_pattern = dp.get("filter_pattern")
        if filter_pattern:
            filter_chain = FilterChain(
                filters=[URLPatternFilter(patterns=[filter_pattern])]
            )
            strategy_kwargs["filter_chain"] = filter_chain

        strategy = BFSDeepCrawlStrategy(**strategy_kwargs)
        config_kwargs["deep_crawl_strategy"] = strategy

    config = CrawlerRunConfig(**config_kwargs)
    crawler = await _get_crawler()

    try:
        url = urls[0]
        result = await crawler.arun(url, config=config)

        if deep_crawl_spec:
            # Deep crawl with arun returns a list of results
            results_list = result if isinstance(result, list) else [result]
            pages = []
            for r in results_list:
                links_list = []
                if hasattr(r, "links") and r.links:
                    for category in ["internal", "external"]:
                        for link in r.links.get(category, []):
                            links_list.append({"href": link.get("href", "")})

                pages.append({
                    "url": r.url,
                    "title": getattr(r, "title", "") or "",
                    "markdown": r.markdown or "",
                    "links": links_list,
                    "media": [],
                })
            return JSONResponse(pages)
        else:
            links = []
            if hasattr(result, "links") and result.links:
                for category in ["internal", "external"]:
                    for link in result.links.get(category, []):
                        links.append({"href": link.get("href", "")})

            media = []
            if hasattr(result, "media") and result.media:
                for img in result.media.get("images", []):
                    media.append({"src": img.get("src", "")})

            return JSONResponse({
                "markdown": result.markdown or "",
                "links": links,
                "media": media,
            })

    except Exception as e:
        logger.error(f"Crawl error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.on_event("shutdown")
async def shutdown():
    global _crawler
    if _crawler:
        await _crawler.__aexit__(None, None, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=11235, log_level="info")
