"""
Integration test fixtures — real Gemini, real Firestore, real ADK.

All fixtures are session-scoped so the expensive discovery pipeline
only runs once per business across all test levels.

Requires: GEMINI_API_KEY env var set.
Optional: GOOGLE_APPLICATION_CREDENTIALS for Firestore tests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

import pytest
import pytest_asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from backend.agents.discovery import discovery_pipeline
from backend.agents.discovery.locator import LocatorAgent
from backend.lib.adk_helpers import user_msg
from backend.tests.integration.businesses import BUSINESSES, GroundTruth

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Skip entire module if no API key
# ------------------------------------------------------------------

def _is_cloud_run() -> bool:
    """Detect Cloud Run environment (K_SERVICE for services, CLOUD_RUN_JOB for jobs)."""
    return bool(os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: real API integration tests (requires GEMINI_API_KEY)")
    config.addinivalue_line("markers", "needs_browser: tests that need Playwright/crawl4ai (skip on Cloud Run)")


def pytest_collection_modifyitems(config, items):
    if not os.environ.get("GEMINI_API_KEY"):
        skip = pytest.mark.skip(reason="GEMINI_API_KEY not set")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)

    if _is_cloud_run():
        skip_browser = pytest.mark.skip(
            reason="Cloud Run: no Playwright browser binary or crawl4ai sidecar available"
        )
        for item in items:
            if "needs_browser" in item.keywords:
                item.add_marker(skip_browser)


# ------------------------------------------------------------------
# Session-scoped cache for expensive pipeline results
# ------------------------------------------------------------------

class DiscoveryCache:
    """Shared cache so pipeline results are reused across test levels."""

    def __init__(self):
        self.locator_results: dict[str, dict] = {}
        self.pipeline_states: dict[str, dict] = {}
        self.enriched_profiles: dict[str, dict] = {}


@pytest.fixture(scope="session")
def discovery_cache():
    return DiscoveryCache()


# ------------------------------------------------------------------
# Business parametrization
# ------------------------------------------------------------------

@pytest.fixture(params=BUSINESSES, ids=lambda b: b.id, scope="session")
def business(request) -> GroundTruth:
    return request.param


# Subsets for targeted tests
@pytest.fixture(
    params=[b for b in BUSINESSES if b.is_restaurant],
    ids=lambda b: b.id,
    scope="session",
)
def restaurant(request) -> GroundTruth:
    return request.param


@pytest.fixture(
    params=[b for b in BUSINESSES if not b.is_restaurant],
    ids=lambda b: b.id,
    scope="session",
)
def non_restaurant(request) -> GroundTruth:
    return request.param


# ------------------------------------------------------------------
# ADK Runner factory
# ------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def runner_factory():
    """Create an ADK Runner + session for the discovery pipeline."""

    async def _create():
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="integration-test",
            agent=discovery_pipeline,
            session_service=session_service,
        )
        session_id = f"integ-{int(time.time() * 1000)}"
        user_id = "test-user"

        await session_service.create_session(
            app_name="integration-test",
            user_id=user_id,
            session_id=session_id,
            state={},
        )
        return runner, session_service, user_id, session_id

    return _create


# ------------------------------------------------------------------
# Enriched profile builder (mirrors discover.py lines 107-166)
# ------------------------------------------------------------------

def _safe_parse(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        return json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
    except (json.JSONDecodeError, ValueError):
        return {}


def _safe_parse_array(value) -> list:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(re.sub(r"```json\n?|\n?```", "", value).strip())
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


# ------------------------------------------------------------------
# Pre-warm all 5 pipelines concurrently (biggest speed win)
# ------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prewarm_pipelines(discovery_cache, runner_factory):
    """Run all 5 discovery pipelines in parallel at session start.

    This cuts total test time from ~900s (sequential) to ~180s (parallel).
    Each pipeline result is cached so individual tests hit the cache.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return

    async def _run_one(biz: GroundTruth):
        try:
            logger.info(f"[Prewarm/{biz.id}] Starting locator + pipeline...")
            identity = await LocatorAgent.resolve(biz.query)
            discovery_cache.locator_results[biz.id] = identity

            runner, session_service, user_id, session_id = await runner_factory()
            prompt = (
                f"Please discover everything about this business:\n"
                f"Name: {identity.get('name', biz.name)}\n"
                f"Address: {identity.get('address', '')}\n"
                f"URL: {identity.get('officialUrl', '')}"
            )

            async for _ in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_msg(prompt),
            ):
                pass

            final_session = await session_service.get_session(
                app_name="integration-test", user_id=user_id, session_id=session_id
            )
            state = final_session.state if final_session else {}
            discovery_cache.pipeline_states[biz.id] = state
            discovery_cache.enriched_profiles[biz.id] = build_enriched_profile(identity, state)
            logger.info(f"[Prewarm/{biz.id}] Done — state keys: {list(state.keys())}")
        except Exception as e:
            logger.warning(f"[Prewarm/{biz.id}] Failed: {e}")

    await asyncio.gather(*[_run_one(biz) for biz in BUSINESSES])


def build_enriched_profile(identity: dict, state: dict) -> dict:
    """Build enriched profile from pipeline state, mirroring discover.py."""
    th = _safe_parse(state.get("themeData"))
    cd = _safe_parse(state.get("contactData"))
    sd = _safe_parse(state.get("socialData"))
    md = _safe_parse(state.get("menuData"))
    maps_url = state.get("mapsData", "")
    if isinstance(maps_url, str):
        maps_url = re.sub(r'```json\n?|\n?```', "", maps_url).replace('"', "").strip()

    parsed_competitors = _safe_parse_array(state.get("competitorData"))
    social_profile_metrics = _safe_parse(state.get("socialProfileMetrics"))

    return {
        **identity,
        "menuUrl": md.get("menuUrl") or None,
        "socialLinks": {
            "instagram": sd.get("instagram") or None,
            "facebook": sd.get("facebook") or None,
            "twitter": sd.get("twitter") or None,
            "yelp": sd.get("yelp") or None,
            "tiktok": sd.get("tiktok") or None,
            "grubhub": md.get("grubhub") or sd.get("grubhub") or None,
            "doordash": md.get("doordash") or sd.get("doordash") or None,
            "ubereats": md.get("ubereats") or sd.get("ubereats") or None,
            "seamless": md.get("seamless") or sd.get("seamless") or None,
            "toasttab": md.get("toasttab") or sd.get("toasttab") or None,
        },
        "phone": cd.get("phone") or sd.get("phone") or None,
        "email": cd.get("email") or sd.get("email") or None,
        "hours": cd.get("hours") or sd.get("hours") or None,
        "googleMapsUrl": maps_url or None,
        "competitors": parsed_competitors if parsed_competitors else None,
        "favicon": th.get("favicon") or None,
        "logoUrl": th.get("logoUrl") or None,
        "primaryColor": th.get("primaryColor") or None,
        "secondaryColor": th.get("secondaryColor") or None,
        "persona": th.get("persona") or None,
        "socialProfileMetrics": social_profile_metrics or None,
    }
