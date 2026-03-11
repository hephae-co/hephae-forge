"""
Shared pytest fixtures for backend tests.

Provides an async HTTPX test client that calls the FastAPI app in-process,
plus common mock fixtures for ADK, GCS, Firestore, and BigQuery.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """Async test client that speaks directly to the FastAPI app."""
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_runner():
    """Mock the ADK Runner so no Gemini calls are made."""

    async def _empty_stream(*args, **kwargs):
        return
        yield  # make it an async generator

    runner_instance = MagicMock()
    runner_instance.run_async = MagicMock(side_effect=_empty_stream)

    with patch("google.adk.runners.Runner", return_value=runner_instance) as mock_cls:
        mock_cls._instance = runner_instance
        yield runner_instance


@pytest.fixture
def mock_session_service():
    """Mock the ADK InMemorySessionService."""
    svc = MagicMock()
    svc.create_session = AsyncMock(return_value=None)
    svc.get_session = AsyncMock(return_value=MagicMock(state={}))

    with patch("google.adk.sessions.InMemorySessionService", return_value=svc) as mock_cls:
        mock_cls._instance = svc
        yield svc


@pytest.fixture
def mock_storage():
    """Mock report storage (GCS upload) and slug generation."""
    with (
        patch(
            "hephae_common.report_storage.generate_slug",
            side_effect=lambda name: name.lower().replace(" ", "-"),
        ) as mock_slug,
        patch(
            "hephae_common.report_storage.upload_report",
            new_callable=AsyncMock,
            return_value="https://storage.googleapis.com/test/report.html",
        ) as mock_upload,
    ):
        yield {"generate_slug": mock_slug, "upload_report": mock_upload}


@pytest.fixture
def mock_db():
    """Mock all DB write functions."""
    with (
        patch(
            "hephae_db.firestore.agent_results.write_agent_result",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_war,
        patch(
            "hephae_db.firestore.discovery.write_discovery",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_wd,
        patch(
            "hephae_db.firestore.interactions.write_interaction",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_wi,
    ):
        yield {
            "write_agent_result": mock_war,
            "write_discovery": mock_wd,
            "write_interaction": mock_wi,
        }
