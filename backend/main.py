"""
FastAPI application — main entry point.

Mounts all routers under /api to match the Next.js route structure.
Next.js proxies /api/* requests here via rewrites().
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(".env.local")
load_dotenv()  # also load .env if it exists

app = FastAPI(
    title="Hephae Forge API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://insights.ai.hephae.co",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Router registration (lazy imports to avoid circular deps) ---


def _register_routers() -> None:
    from backend.routers import discover, analyze, chat, track, send_report_email, social_card, social_posts, places, optimize
    from backend.routers.capabilities import seo, competitive, traffic, marketing
    from backend.routers.v1 import (
        discover as v1_discover,
        analyze as v1_analyze,
        seo as v1_seo,
        competitive as v1_competitive,
        traffic as v1_traffic,
    )

    app.include_router(track.router, prefix="/api")
    app.include_router(places.router, prefix="/api")
    app.include_router(send_report_email.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(discover.router, prefix="/api")
    app.include_router(social_card.router, prefix="/api")
    app.include_router(social_posts.router, prefix="/api")
    app.include_router(analyze.router, prefix="/api")
    app.include_router(seo.router, prefix="/api")
    app.include_router(competitive.router, prefix="/api")
    app.include_router(traffic.router, prefix="/api")
    app.include_router(marketing.router, prefix="/api")
    app.include_router(optimize.router, prefix="/api")
    app.include_router(v1_discover.router, prefix="/api")
    app.include_router(v1_analyze.router, prefix="/api")
    app.include_router(v1_seo.router, prefix="/api")
    app.include_router(v1_competitive.router, prefix="/api")
    app.include_router(v1_traffic.router, prefix="/api")


_register_routers()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "marginsurgeon-backend"}
