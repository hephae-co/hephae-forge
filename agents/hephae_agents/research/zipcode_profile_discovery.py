"""Zipcode Profile Discovery — two-phase source enumeration + verification.

Phase 1: Enumerate sources (deterministic API checks + LLM google_search)
Phase 2: Verify each confirmed source (LLM + crawl4ai, semaphore of 3)
Output:  ZipcodeProfile saved to Firestore zipcode_profiles collection

This is NOT an ADK agent tree — it's a plain async orchestrator that uses
run_agent_to_json for standalone LLM calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import RunConfig
from google.adk.tools import google_search

from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_db.schemas.zipcode_profile import SourceCandidate, SourceEntry, ZipcodeProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Master Source Taxonomy — static checklist of ~30 source categories
# ---------------------------------------------------------------------------

MASTER_SOURCE_TAXONOMY: dict[str, dict[str, Any]] = {
    # === MUNICIPAL GOVERNMENT ===
    "municipal_website": {
        "description": "Official city/town/township/borough government website",
        "search_template": "{city} {state} official website government",
        "always_exists": True,
    },
    "planning_zoning_board": {
        "description": "Planning board, zoning board, or land use board",
        "search_template": "{city} {state} planning board zoning applications",
        "subpages": ["agendas", "minutes", "applications", "decisions"],
    },
    "public_works_dpw": {
        "description": "Dept of Public Works — road closures, paving, utilities",
        "search_template": "{city} {state} department public works DPW",
        "subpages": ["road-closures", "paving-schedule", "water-sewer"],
    },
    "building_permits": {
        "description": "Building department — permit applications, inspections",
        "search_template": "{city} {state} building department permits",
    },
    "recreation_events": {
        "description": "Recreation department / events calendar",
        "search_template": "{city} {state} recreation events calendar",
    },
    "municipal_budget": {
        "description": "Municipal budget and financial documents",
        "search_template": "{city} {state} municipal budget financial documents",
    },
    "meeting_minutes": {
        "description": "Town council / board of commissioners meeting minutes",
        "search_template": "{city} {state} council meeting minutes agendas",
    },
    "municipal_rss": {
        "description": "Any RSS or Atom feeds from the municipality",
        "search_template": "{city} {state} municipal rss feed atom",
    },
    # === COUNTY GOVERNMENT ===
    "county_health_dept": {
        "description": "County health department — inspections, permits, data",
        "search_template": "{county} county {state} health department restaurant inspections",
    },
    "county_clerk": {
        "description": "County clerk — business filings, property records",
        "search_template": "{county} county {state} clerk records online",
    },
    "county_planning": {
        "description": "County planning board — major development applications",
        "search_template": "{county} county {state} planning board applications",
    },
    "county_economic_dev": {
        "description": "County economic development office — grants, programs",
        "search_template": "{county} county {state} economic development office",
    },
    # === STATE GOVERNMENT ===
    "state_legal_notices": {
        "description": "Centralized legal notice portal (NJ DOS, etc.)",
        "search_template": "{state} statewide legal notices portal government",
    },
    "state_business_registry": {
        "description": "State business entity search / registration",
        "search_template": "{state} business entity search registration",
    },
    # === LOCAL NEWS & MEDIA ===
    "patch_com": {
        "description": "Patch.com hyperlocal news community",
        "search_template": "site:patch.com {city} {state}",
    },
    "tapinto": {
        "description": "TAPinto local news network",
        "search_template": "site:tapinto.net {city}",
    },
    "local_newspaper": {
        "description": "Local/community newspaper (print or online)",
        "search_template": "{city} {state} local newspaper community news",
    },
    "municipal_newsletter": {
        "description": "Town newsletter, bulletin, or email blast archive",
        "search_template": "{city} {state} municipal newsletter bulletin",
    },
    # === BUSINESS & ECONOMIC ORGANIZATIONS ===
    "chamber_of_commerce": {
        "description": "Local chamber of commerce",
        "search_template": "{city} {state} chamber of commerce",
    },
    "business_improvement_district": {
        "description": "BID / Business Improvement District / SID",
        "search_template": "{city} {state} business improvement district BID downtown",
    },
    "downtown_development": {
        "description": "Downtown development corporation / Main Street program",
        "search_template": "{city} {state} downtown development main street program",
    },
    "economic_development_corp": {
        "description": "Local or regional economic development corporation",
        "search_template": "{city} OR {county} {state} economic development corporation",
    },
    "merchants_association": {
        "description": "Local merchants association or business alliance",
        "search_template": "{city} {state} merchants association business alliance",
    },
    # === COMMUNITY & CIVIC ===
    "library_system": {
        "description": "Public library — events calendar, community programs",
        "search_template": "{city} {state} public library events calendar",
    },
    "school_district": {
        "description": "School district — calendar, closings, enrollment data",
        "search_template": "{city} {state} school district calendar",
    },
    "community_calendar": {
        "description": "Unified community events calendar (if separate from municipal)",
        "search_template": "{city} {state} community events calendar 2026",
    },
    # === SOCIAL MEDIA & FORUMS ===
    "local_subreddit": {
        "description": "Town/city-specific subreddit",
        "search_template": "site:reddit.com r/{city_slug}",
    },
    "state_subreddit": {
        "description": "State-level subreddit (fallback for towns without their own)",
        "search_template": "site:reddit.com r/{state_slug}",
        "always_exists": True,
    },
    "facebook_community_groups": {
        "description": "Local Facebook groups (names only — can't access content)",
        "search_template": "{city} {state} facebook community group",
    },
    # === FEDERAL/API DATA SOURCES ===
    "census_acs": {
        "description": "Census American Community Survey — demographics, income",
        "check": "api_call",
    },
    "google_trends": {
        "description": "Google Trends via BigQuery — DMA-level search interest",
        "check": "dma_lookup",
    },
    "nws_weather": {
        "description": "National Weather Service — nearest station for forecasts",
        "check": "api_call",
    },
    "osm_businesses": {
        "description": "OpenStreetMap — local business counts and categories",
        "check": "api_call",
    },
    "fema_declarations": {
        "description": "FEMA disaster declarations for the area",
        "check": "api_call",
    },
}


# ---------------------------------------------------------------------------
# LLM Agent definitions (standalone — not part of an agent tree)
# ---------------------------------------------------------------------------

ENUMERATOR_INSTRUCTION = """You are a local data source researcher. Your job is to determine which
data sources exist for a specific city/town/locality.

You will be given a list of source categories with search templates. For each category:
1. Execute the search query (adapted for the target city/state/county)
2. Evaluate if a real, relevant result exists for THIS specific locality
3. If found, capture the most relevant URL

Return a JSON array of objects, one per category:
[
  {
    "category": "municipal_website",
    "exists": true,
    "searchEvidence": "Found official website at nutleynj.org",
    "candidateUrl": "https://www.nutleynj.org"
  },
  {
    "category": "business_improvement_district",
    "exists": false,
    "searchEvidence": "No BID or SID found for this town",
    "candidateUrl": ""
  }
]

IMPORTANT:
- Be accurate — only mark exists=true if there's a real, active result for THIS locality
- For news sites (patch, tapinto), verify the specific town has coverage, not just the parent site
- For subreddits, verify the specific subreddit exists (not just search results about the town)
- Capture the most specific/direct URL as candidateUrl
- searchEvidence should be a brief (1-sentence) explanation of what you found or didn't find
"""

_source_enumerator = LlmAgent(
    name="source_enumerator",
    model=AgentModels.PRIMARY_MODEL,
    instruction=ENUMERATOR_INSTRUCTION,
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)


VERIFIER_INSTRUCTION = """You are a source verification agent. Given a candidate data source (category + URL),
verify it exists, is active, and capture its specific details.

Your verification steps:
1. Navigate to the candidateUrl
2. Confirm it's a real, active page (not a 404 or redirect to a generic page)
3. Look for key subpages, feeds, or features specific to this source type
4. Capture specific URLs for subpages, events calendars, feeds, etc.

Return a JSON object with the verified source details:
{
  "category": "municipal_website",
  "status": "verified",
  "url": "https://www.nutleynj.org",
  "subpages": {
    "planning_board": "https://www.nutleynj.org/planning-board",
    "dpw": "https://www.nutleynj.org/dpw"
  },
  "active": true,
  "hasOnlinePortal": false,
  "accessType": "",
  "eventsUrl": "",
  "calendarUrl": "",
  "note": ""
}

Rules:
- status must be one of: "verified", "not_found", "pdf_only"
- "verified" = real, active, usable page
- "not_found" = URL is dead, generic, or not actually for this source
- "pdf_only" = data exists but only as downloadable PDFs (not machine-readable)
- Only include subpages you actually found — don't guess
- eventsUrl/calendarUrl should be direct links to events/calendar pages if found
- note should explain any caveats (e.g., "permit applications require in-person visit")
"""

_source_verifier = LlmAgent(
    name="source_verifier",
    model=AgentModels.PRIMARY_MODEL,
    instruction=VERIFIER_INSTRUCTION,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Phase 1: Deterministic API checks
# ---------------------------------------------------------------------------


async def _check_api_sources(
    zip_code: str,
    city: str,
    state: str,
    county: str,
    latitude: float,
    longitude: float,
    dma_name: str,
) -> dict[str, SourceEntry]:
    """Run deterministic API checks for sources marked check: 'api_call' / 'dma_lookup'."""
    results: dict[str, SourceEntry] = {}
    now = datetime.utcnow().isoformat()

    # Census ACS
    try:
        from hephae_db.bigquery.public_data import query_census_demographics

        data = await query_census_demographics(zip_code)
        if data and data.get("totalPopulation", 0) > 0:
            results["census_acs"] = SourceEntry(
                status="verified", active=True, lastVerified=now,
                note=f"pop={data.get('totalPopulation', 0)}, income=${data.get('medianHouseholdIncome', 0):,}",
            )
        else:
            results["census_acs"] = SourceEntry(status="not_found", lastVerified=now)
    except Exception as e:
        logger.warning(f"[ProfileDiscovery] Census ACS check failed: {e}")
        results["census_acs"] = SourceEntry(status="not_found", note=str(e))

    # OSM Business Density
    try:
        from hephae_db.bigquery.public_data import query_osm_business_density

        data = await query_osm_business_density(latitude, longitude)
        total = data.get("totalBusinesses", 0) if data else 0
        if total > 0:
            results["osm_businesses"] = SourceEntry(
                status="verified", active=True, lastVerified=now,
                note=f"{total} businesses within 1500m",
            )
        else:
            results["osm_businesses"] = SourceEntry(status="not_found", lastVerified=now)
    except Exception as e:
        logger.warning(f"[ProfileDiscovery] OSM check failed: {e}")
        results["osm_businesses"] = SourceEntry(status="not_found", note=str(e))

    # NWS Weather (via NOAA historical)
    try:
        from hephae_db.bigquery.public_data import query_noaa_weather_history

        data = await query_noaa_weather_history(latitude, longitude)
        if data and data.get("observationDays", 0) > 0:
            results["nws_weather"] = SourceEntry(
                status="verified", active=True, lastVerified=now,
                note=f"station={data.get('station', '')}, dist={data.get('stationDistKm', 0)}km",
            )
        else:
            results["nws_weather"] = SourceEntry(status="not_found", lastVerified=now)
    except Exception as e:
        logger.warning(f"[ProfileDiscovery] NWS check failed: {e}")
        results["nws_weather"] = SourceEntry(status="not_found", note=str(e))

    # Google Trends (DMA lookup)
    if dma_name:
        results["google_trends"] = SourceEntry(
            status="verified", active=True, lastVerified=now,
            note=f"DMA: {dma_name}",
        )
    else:
        results["google_trends"] = SourceEntry(
            status="not_found", lastVerified=now,
            note="No DMA mapping available",
        )

    # FEMA Declarations
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            fips = f"{state}"  # Simplified — uses state-level check
            resp = await client.get(
                f"https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
                params={"$filter": f"state eq '{state}'", "$top": 1, "$orderby": "declarationDate desc"},
            )
            if resp.status_code == 200:
                data = resp.json()
                declarations = data.get("DisasterDeclarationsSummaries", [])
                if declarations:
                    results["fema_declarations"] = SourceEntry(
                        status="verified", active=True, lastVerified=now,
                        note=f"Latest: {declarations[0].get('declarationTitle', 'N/A')}",
                    )
                else:
                    results["fema_declarations"] = SourceEntry(status="not_found", lastVerified=now)
            else:
                results["fema_declarations"] = SourceEntry(status="not_found", lastVerified=now)
    except Exception as e:
        logger.warning(f"[ProfileDiscovery] FEMA check failed: {e}")
        results["fema_declarations"] = SourceEntry(status="not_found", note=str(e))

    return results


# ---------------------------------------------------------------------------
# Phase 1: LLM enumeration of search-based sources
# ---------------------------------------------------------------------------


def _build_enumeration_prompt(
    city: str,
    state: str,
    county: str,
    taxonomy: dict[str, dict[str, Any]],
    api_checked: set[str],
) -> str:
    """Build the enumeration prompt for the LLM agent."""
    categories_to_check = []
    for cat, meta in taxonomy.items():
        if cat in api_checked:
            continue  # Already checked via API
        if meta.get("check") in ("api_call", "dma_lookup"):
            continue  # Will be checked via API

        # Substitute template variables
        template = meta.get("search_template", "")
        city_slug = city.lower().replace(" ", "")
        state_slug = state.lower().replace(" ", "")
        template = template.replace("{city}", city)
        template = template.replace("{state}", state)
        template = template.replace("{county}", county)
        template = template.replace("{city_slug}", city_slug)
        template = template.replace("{state_slug}", state_slug)

        categories_to_check.append({
            "category": cat,
            "description": meta["description"],
            "search_query": template,
            "always_exists": meta.get("always_exists", False),
        })

    return (
        f"Research data sources for: {city}, {state} (County: {county})\n\n"
        f"Check each of the following {len(categories_to_check)} source categories.\n"
        f"For categories marked always_exists=true, add them as exists=true but still find the URL.\n"
        f"For all others, use the search_query to determine if a real source exists.\n\n"
        f"Categories to check:\n{json.dumps(categories_to_check, indent=2)}\n\n"
        f"Return a JSON array with one object per category (all {len(categories_to_check)} categories must be included)."
    )


async def _enumerate_sources(
    city: str,
    state: str,
    county: str,
    api_checked: set[str],
) -> list[SourceCandidate]:
    """Phase 1: Use LLM + google_search to enumerate which sources exist."""
    prompt = _build_enumeration_prompt(city, state, county, MASTER_SOURCE_TAXONOMY, api_checked)

    result = await run_agent_to_json(
        agent=_source_enumerator,
        prompt=prompt,
        app_name="ZipcodeProfileDiscovery",
        run_config=RunConfig(max_llm_calls=15),
    )

    if not result:
        logger.error("[ProfileDiscovery] Enumerator returned no results")
        return []

    # Parse result — could be list of dicts or list of SourceCandidate
    candidates = []
    items = result if isinstance(result, list) else [result]
    for item in items:
        if isinstance(item, dict):
            candidates.append(SourceCandidate(**item))
        elif isinstance(item, SourceCandidate):
            candidates.append(item)

    logger.info(
        f"[ProfileDiscovery] Enumerated {len(candidates)} sources, "
        f"{sum(1 for c in candidates if c.exists)} confirmed"
    )
    return candidates


# ---------------------------------------------------------------------------
# Phase 2: Verify each confirmed source
# ---------------------------------------------------------------------------


async def _verify_single_source(
    candidate: SourceCandidate,
    city: str,
    state: str,
    semaphore: asyncio.Semaphore,
) -> SourceEntry:
    """Verify a single source candidate via LLM + crawl4ai."""
    async with semaphore:
        meta = MASTER_SOURCE_TAXONOMY.get(candidate.category, {})
        subpages_hint = meta.get("subpages", [])

        prompt = (
            f"Verify this data source for {city}, {state}:\n"
            f"Category: {candidate.category}\n"
            f"Description: {meta.get('description', candidate.category)}\n"
            f"Candidate URL: {candidate.candidateUrl}\n"
            f"Search evidence: {candidate.searchEvidence}\n"
        )
        if subpages_hint:
            prompt += f"Look for these subpages: {', '.join(subpages_hint)}\n"
        prompt += "\nVerify the URL is real and active, then capture specific details."

        try:
            result = await run_agent_to_json(
                agent=_source_verifier,
                prompt=prompt,
                app_name="ZipcodeProfileDiscovery",
                run_config=RunConfig(max_llm_calls=8),
            )

            if result and isinstance(result, dict):
                # Ensure category is correct
                result["category"] = candidate.category
                return SourceEntry(
                    status=result.get("status", "not_found"),
                    url=result.get("url", candidate.candidateUrl),
                    lastVerified=datetime.utcnow().isoformat(),
                    subpages=result.get("subpages", {}),
                    active=result.get("active"),
                    hasOnlinePortal=result.get("hasOnlinePortal"),
                    accessType=result.get("accessType", ""),
                    eventsUrl=result.get("eventsUrl", ""),
                    calendarUrl=result.get("calendarUrl", ""),
                    note=result.get("note", ""),
                )
        except Exception as e:
            logger.error(f"[ProfileDiscovery] Verification failed for {candidate.category}: {e}")

        # Fallback: mark as verified with candidate URL if we had evidence
        return SourceEntry(
            status="verified" if candidate.candidateUrl else "not_found",
            url=candidate.candidateUrl,
            lastVerified=datetime.utcnow().isoformat(),
            note="Verification agent failed — using enumeration data",
        )


async def _verify_sources(
    candidates: list[SourceCandidate],
    city: str,
    state: str,
) -> dict[str, SourceEntry]:
    """Phase 2: Verify all confirmed sources with concurrency limit."""
    confirmed = [c for c in candidates if c.exists and c.candidateUrl]
    if not confirmed:
        return {}

    semaphore = asyncio.Semaphore(3)
    tasks = [
        _verify_single_source(candidate, city, state, semaphore)
        for candidate in confirmed
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    verified: dict[str, SourceEntry] = {}
    for candidate, result in zip(confirmed, results):
        if isinstance(result, Exception):
            logger.error(f"[ProfileDiscovery] Verify error for {candidate.category}: {result}")
            verified[candidate.category] = SourceEntry(
                status="not_found",
                note=f"Verification error: {result}",
            )
        else:
            verified[candidate.category] = result

    # Also add not-found entries for candidates that existed but had no URL
    for c in candidates:
        if c.exists and not c.candidateUrl and c.category not in verified:
            verified[c.category] = SourceEntry(
                status="verified",
                lastVerified=datetime.utcnow().isoformat(),
                note=c.searchEvidence,
            )

    return verified


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_zipcode_profile_discovery(zip_code: str) -> dict[str, Any]:
    """Run full two-phase discovery for a zip code and save the profile.

    Phase 1: Deterministic API checks + LLM enumeration
    Phase 2: Verify each confirmed source via LLM + crawl4ai
    Output:  ZipcodeProfile saved to Firestore

    Returns the profile dict.
    """
    logger.info(f"[ProfileDiscovery] Starting discovery for {zip_code}")

    # Step 1: Resolve geography
    from hephae_db.bigquery.public_data import resolve_zip_geography

    geo = await resolve_zip_geography(zip_code)
    if not geo:
        logger.error(f"[ProfileDiscovery] Cannot resolve geography for {zip_code}")
        return {"error": f"Cannot resolve geography for {zip_code}"}

    city = geo.city
    state = geo.state_code
    county = geo.county
    latitude = geo.latitude
    longitude = geo.longitude

    # Resolve DMA (best effort)
    dma_name = ""
    try:
        from hephae_db.bigquery.public_data import _run_query
        from google.cloud import bigquery as bq

        dma_rows = await _run_query(
            """
            SELECT dma_name FROM `bigquery-public-data.utility_us.zipcode_area`
            WHERE zipcode = @zip LIMIT 1
            """,
            params=[bq.ScalarQueryParameter("zip", "STRING", zip_code)],
        )
        if dma_rows and dma_rows[0].get("dma_name"):
            dma_name = dma_rows[0]["dma_name"]
    except Exception:
        pass

    logger.info(f"[ProfileDiscovery] Geography: {city}, {state} ({county} County), DMA: {dma_name or 'N/A'}")

    # Step 2: Phase 1 — deterministic API checks
    api_results = await _check_api_sources(
        zip_code, city, state, county, latitude, longitude, dma_name,
    )
    api_checked = set(api_results.keys())
    logger.info(f"[ProfileDiscovery] Phase 1 API: {len(api_results)} sources checked")

    # Step 3: Phase 1 — LLM enumeration
    candidates = await _enumerate_sources(city, state, county, api_checked)

    # Step 4: Phase 2 — verify confirmed sources
    verified = await _verify_sources(candidates, city, state)
    logger.info(f"[ProfileDiscovery] Phase 2: {len(verified)} sources verified")

    # Step 5: Assemble the profile
    now = datetime.utcnow()
    all_sources: dict[str, SourceEntry] = {}

    # Add API-checked sources
    for cat, entry in api_results.items():
        all_sources[cat] = entry

    # Add verified sources
    for cat, entry in verified.items():
        all_sources[cat] = entry

    # Add not-found entries for categories not checked or verified
    for candidate in candidates:
        if candidate.category not in all_sources:
            all_sources[candidate.category] = SourceEntry(
                status="not_found" if not candidate.exists else "verified",
                lastVerified=now.isoformat(),
                note=candidate.searchEvidence,
            )

    # Build unavailable list
    unavailable = []
    confirmed_count = 0
    unavailable_count = 0
    for cat, entry in all_sources.items():
        if entry.status in ("verified",):
            confirmed_count += 1
        else:
            unavailable_count += 1
            label = f"{cat}: {entry.status}"
            if entry.note:
                label += f" ({entry.note})"
            unavailable.append(label)

    profile = ZipcodeProfile(
        zipCode=zip_code,
        city=city,
        state=state,
        county=county,
        dmaName=dma_name,
        profileVersion="1.0",
        discoveredAt=now.isoformat(),
        refreshAfter=(now + timedelta(days=90)).isoformat(),
        enumeratedSources=len(all_sources),
        confirmedSources=confirmed_count,
        unavailableSources=unavailable_count,
        sources=all_sources,
        unavailable=unavailable,
    )

    # Step 6: Save to Firestore
    profile_dict = profile.model_dump()
    # Convert SourceEntry models to plain dicts for Firestore
    profile_dict["sources"] = {
        k: v.model_dump(exclude_none=True) for k, v in all_sources.items()
    }

    from hephae_db.firestore.zipcode_profiles import save_zipcode_profile

    await save_zipcode_profile(profile_dict)

    logger.info(
        f"[ProfileDiscovery] Complete for {zip_code}: "
        f"{confirmed_count} confirmed, {unavailable_count} unavailable "
        f"(out of {len(all_sources)} total)"
    )

    return profile_dict
