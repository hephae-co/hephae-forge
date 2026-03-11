"""Unified FastAPI application — merged web + admin backend.

Both web-ui and admin-ui call this single API service.
Capabilities are direct Python imports (no inter-service HTTP).
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings

load_dotenv(".env.local")
load_dotenv()

# ── Request trace ID ──────────────────────────────────────────────────────
# Each request gets a unique trace ID for log correlation across modules.
# Access from anywhere: from backend.main import trace_id; trace_id.get()
trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


class _TraceFilter(logging.Filter):
    """Injects trace_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id.get()  # type: ignore[attr-defined]
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s [%(trace_id)s] %(message)s",
)
# Add the filter to the root logger so all child loggers inherit it
logging.getLogger().addFilter(_TraceFilter())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Firebase on startup."""
    from hephae_common.firebase import get_db
    get_db()
    logger.info("Unified API started — Firebase initialized")
    yield
    logger.info("Unified API shutting down")


app = FastAPI(
    title="Hephae Unified API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — environment-based origins
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TraceMiddleware(BaseHTTPMiddleware):
    """Assign a short trace ID to every request for log correlation."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = trace_id.set(rid)
        response = await call_next(request)
        response.headers["x-trace-id"] = rid
        trace_id.reset(token)
        return response


app.add_middleware(TraceMiddleware)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "hephae-unified-api"}


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Hephae Unified API is running",
        "docs": "/api/docs",
    }


def _register_routers() -> None:
    """Lazy router registration to avoid circular imports."""

    # --- Web routers (serving web frontend) ---
    from backend.routers.web import (
        auth,
        capabilities,
        discover,
        analyze,
        blog,
        social_posts,
        send_report_email,
        chat,
        places,
        track,
        social_card,
        heartbeat,
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(track.router, prefix="/api")
    app.include_router(places.router, prefix="/api")
    app.include_router(send_report_email.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(discover.router, prefix="/api")
    app.include_router(social_card.router, prefix="/api")
    app.include_router(social_posts.router, prefix="/api")
    app.include_router(analyze.router, prefix="/api")
    app.include_router(capabilities.router, prefix="/api")
    app.include_router(blog.router, prefix="/api")
    app.include_router(heartbeat.router, prefix="/api")

    # --- V1 backward-compat routers ---
    from backend.routers.v1 import (
        discover as v1_discover,
        analyze as v1_analyze,
        seo as v1_seo,
        competitive as v1_competitive,
        traffic as v1_traffic,
    )

    app.include_router(v1_discover.router, prefix="/api")
    app.include_router(v1_analyze.router, prefix="/api")
    app.include_router(v1_seo.router, prefix="/api")
    app.include_router(v1_competitive.router, prefix="/api")
    app.include_router(v1_traffic.router, prefix="/api")

    # --- Admin routers (serving admin frontend) ---
    from backend.routers.admin import (
        workflows,
        workflow_stream,
        workflow_actions,
        research_businesses,
        zipcode_research,
        area_research,
        sector_research,
        combined_context,
        stats,
        fixtures,
        test_runner,
        food_prices,
        content,
        discovery_jobs,
        tasks,
    )

    app.include_router(workflows.router)
    app.include_router(workflow_stream.router)
    app.include_router(workflow_actions.router)
    app.include_router(research_businesses.router)
    app.include_router(zipcode_research.router)
    app.include_router(area_research.router)
    app.include_router(sector_research.router)
    app.include_router(combined_context.router)
    app.include_router(stats.router)
    app.include_router(fixtures.router)
    app.include_router(test_runner.router)
    app.include_router(food_prices.router)
    app.include_router(content.router)
    app.include_router(discovery_jobs.router)
    app.include_router(tasks.router)

    # --- Batch / Cron routers ---
    from backend.routers.batch import cron, heartbeat_cron

    app.include_router(cron.router)
    app.include_router(heartbeat_cron.router)


_register_routers()
