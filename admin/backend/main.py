"""FastAPI application — hephae-admin backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Firebase on startup."""
    from backend.lib.firebase import get_db
    get_db()
    logger.info("Backend started — Firebase initialized")
    yield
    logger.info("Backend shutting down")


app = FastAPI(
    title="Hephae Admin API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "hephae-admin-api"}


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Hephae Admin Python Backend is running",
        "docs": "/docs",
    }


def _register_routers():
    """Lazy router registration — import routers only when needed to avoid circular imports."""
    from backend.routers import (
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
        cron,
        food_prices,
        content,
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
    app.include_router(cron.router)
    app.include_router(food_prices.router)
    app.include_router(content.router)


_register_routers()
