"""Zipcode Profile Discovery — ADK agent tree for source enumeration + verification.

Architecture (factory pattern — fresh tree per invocation):
  create_discovery_agent() -> SequentialAgent:
    Stage 1: APISourceChecker (BaseAgent, no LLM) — deterministic API/BQ checks
    Stage 2: SourceEnumerator (LlmAgent + google_search) — searches all non-API categories
    Stage 3: VerificationRouter (BaseAgent, no LLM) — splits into light vs deep
    Stage 4a: CrawlVerifierFanOut (ParallelAgent, 5 agents) — google_search + crawl4ai
    Stage 4b: SearchVerifierFanOut (ParallelAgent, 7 agents) — google_search only
    Stage 5: ProfileAssembler (BaseAgent, no LLM) — merges + saves to Firestore

Executed via Runner + InMemorySessionService (same pattern as generate_pulse).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.tools import google_search

from hephae_api.config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_db.schemas.zipcode_profile import SourceCandidate, SourceEntry, ZipcodeProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State → DMA mapping (deterministic, no BQ query needed)
# ---------------------------------------------------------------------------

STATE_TO_DMA: dict[str, str] = {
    "NJ": "New York", "NY": "New York", "CT": "New York",
    "PA": "Philadelphia", "DE": "Philadelphia",
    "CA": "Los Angeles", "IL": "Chicago", "TX": "Dallas",
    "MA": "Boston", "FL": "Miami", "GA": "Atlanta",
    "WA": "Seattle", "CO": "Denver", "AZ": "Phoenix",
    "DC": "Washington", "MD": "Washington", "VA": "Washington",
}


# ---------------------------------------------------------------------------
# Deep verification: crawl vs search-only classification
# ---------------------------------------------------------------------------

# These 5 categories need crawl4ai for proper verification
CRAWL_DEEP_CATEGORIES = frozenset({
    "municipal_website",
    "planning_zoning_board",
    "public_works_dpw",
    "chamber_of_commerce",
    "county_health_dept",
})

# These 7 categories only need google_search (no crawl4ai)
SEARCH_ONLY_DEEP_CATEGORIES = frozenset({
    "building_permits",
    "county_clerk",
    "county_planning",
    "county_economic_dev",
    "business_improvement_district",
    "downtown_development",
    "merchants_association",
})


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
# Light vs Deep classification
# ---------------------------------------------------------------------------

LIGHT_VERIFICATION_CATEGORIES = frozenset({
    "patch_com",
    "tapinto",
    "local_newspaper",
    "municipal_newsletter",
    "local_subreddit",
    "state_subreddit",
    "facebook_community_groups",
    "state_legal_notices",
    "state_business_registry",
    "school_district",
    "library_system",
    "community_calendar",
    "recreation_events",
    "municipal_budget",
    "meeting_minutes",
    "municipal_rss",
    "economic_development_corp",
})

DEEP_VERIFICATION_CATEGORIES = frozenset({
    "municipal_website",
    "planning_zoning_board",
    "public_works_dpw",
    "chamber_of_commerce",
    "county_health_dept",
    "building_permits",
    "business_improvement_district",
    "downtown_development",
    "merchants_association",
    "county_clerk",
    "county_planning",
    "county_economic_dev",
})


# ---------------------------------------------------------------------------
# Stage 1: APISourceChecker (BaseAgent — deterministic, no LLM)
# ---------------------------------------------------------------------------


class APISourceChecker(BaseAgent):
    """Deterministic API/BQ checks for Census, OSM, NWS, Trends, FEMA.

    Reads zipCode, city, state, county, latitude, longitude, dmaName from
    session state. Writes results to state via state_delta: {"apiSources": {...}}.
    """

    name: str = "APISourceChecker"
    description: str = "Deterministic API source checks — no LLM."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        zip_code = state.get("zipCode", "")
        city = state.get("city", "")
        st = state.get("state", "")
        county = state.get("county", "")
        latitude = state.get("latitude", 0.0)
        longitude = state.get("longitude", 0.0)
        # Use STATE_TO_DMA map instead of BQ query (column doesn't exist)
        dma_name = state.get("dmaName", "") or STATE_TO_DMA.get(st, "")

        logger.info(f"[APISourceChecker] Running API checks for {zip_code}")

        results: dict[str, dict[str, Any]] = {}
        now = datetime.utcnow().isoformat()

        # Census ACS
        try:
            from hephae_db.bigquery.public_data import query_census_demographics

            data = await query_census_demographics(zip_code)
            if data and data.get("totalPopulation", 0) > 0:
                results["census_acs"] = {
                    "status": "verified", "active": True, "lastVerified": now,
                    "note": f"pop={data.get('totalPopulation', 0)}, income=${data.get('medianHouseholdIncome', 0):,}",
                }
            else:
                results["census_acs"] = {"status": "not_found", "lastVerified": now}
        except Exception as e:
            logger.warning(f"[APISourceChecker] Census ACS check failed: {e}")
            results["census_acs"] = {"status": "not_found", "note": str(e)}

        # OSM Business Density
        try:
            from hephae_db.bigquery.public_data import query_osm_business_density

            data = await query_osm_business_density(latitude, longitude)
            total = data.get("totalBusinesses", 0) if data else 0
            if total > 0:
                results["osm_businesses"] = {
                    "status": "verified", "active": True, "lastVerified": now,
                    "note": f"{total} businesses within 1500m",
                }
            else:
                results["osm_businesses"] = {"status": "not_found", "lastVerified": now}
        except Exception as e:
            logger.warning(f"[APISourceChecker] OSM check failed: {e}")
            results["osm_businesses"] = {"status": "not_found", "note": str(e)}

        # NWS Weather (via NOAA historical)
        try:
            from hephae_db.bigquery.public_data import query_noaa_weather_history

            data = await query_noaa_weather_history(latitude, longitude)
            if data and data.get("observationDays", 0) > 0:
                results["nws_weather"] = {
                    "status": "verified", "active": True, "lastVerified": now,
                    "note": f"station={data.get('station', '')}, dist={data.get('stationDistKm', 0)}km",
                }
            else:
                results["nws_weather"] = {"status": "not_found", "lastVerified": now}
        except Exception as e:
            logger.warning(f"[APISourceChecker] NWS check failed: {e}")
            results["nws_weather"] = {"status": "not_found", "note": str(e)}

        # Google Trends (DMA lookup)
        if dma_name:
            results["google_trends"] = {
                "status": "verified", "active": True, "lastVerified": now,
                "note": f"DMA: {dma_name}",
            }
        else:
            results["google_trends"] = {
                "status": "not_found", "lastVerified": now,
                "note": "No DMA mapping available",
            }

        # FEMA Declarations
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
                    params={
                        "$filter": f"state eq '{st}'",
                        "$top": 1,
                        "$orderby": "declarationDate desc",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    declarations = data.get("DisasterDeclarationsSummaries", [])
                    if declarations:
                        results["fema_declarations"] = {
                            "status": "verified", "active": True, "lastVerified": now,
                            "note": f"Latest: {declarations[0].get('declarationTitle', 'N/A')}",
                        }
                    else:
                        results["fema_declarations"] = {"status": "not_found", "lastVerified": now}
                else:
                    results["fema_declarations"] = {"status": "not_found", "lastVerified": now}
        except Exception as e:
            logger.warning(f"[APISourceChecker] FEMA check failed: {e}")
            results["fema_declarations"] = {"status": "not_found", "note": str(e)}

        logger.info(
            f"[APISourceChecker] Done: {len(results)} API sources checked, "
            f"{sum(1 for v in results.values() if v.get('status') == 'verified')} verified"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"apiSources": results}),
        )


# ---------------------------------------------------------------------------
# Stage 2: SourceEnumerator instruction builder
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


def _enumerator_instruction(ctx) -> str:
    """Build enumeration prompt from session state."""
    state = getattr(ctx, "state", {})
    city = state.get("city", "unknown")
    st = state.get("state", "")
    county = state.get("county", "")

    # Determine which categories were already API-checked
    api_sources = state.get("apiSources", {})
    api_checked = set(api_sources.keys())

    categories_to_check = []
    for cat, meta in MASTER_SOURCE_TAXONOMY.items():
        if cat in api_checked:
            continue
        if meta.get("check") in ("api_call", "dma_lookup"):
            continue

        # Substitute template variables
        template = meta.get("search_template", "")
        city_slug = city.lower().replace(" ", "")
        state_slug = st.lower().replace(" ", "")
        template = template.replace("{city}", city)
        template = template.replace("{state}", st)
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
        f"{ENUMERATOR_INSTRUCTION}\n\n"
        f"Research data sources for: {city}, {st} (County: {county})\n\n"
        f"Check each of the following {len(categories_to_check)} source categories.\n"
        f"For categories marked always_exists=true, add them as exists=true but still find the URL.\n"
        f"For all others, use the search_query to determine if a real source exists.\n\n"
        f"Categories to check:\n{json.dumps(categories_to_check, indent=2)}\n\n"
        f"Return a JSON array with one object per category (all {len(categories_to_check)} categories must be included)."
    )


# ---------------------------------------------------------------------------
# Stage 3: VerificationRouter (BaseAgent — deterministic, no LLM)
# ---------------------------------------------------------------------------


class VerificationRouter(BaseAgent):
    """Splits enumerated sources into light-verified vs deep-verification-needed.

    Light sources: URL from enumeration is sufficient, mark verified immediately.
    Deep sources: need LLM + crawl4ai verification in Stage 4.

    Reads enumeratedSources from state. Writes lightVerified + deepCandidates
    to state via state_delta.
    """

    name: str = "VerificationRouter"
    description: str = "Routes sources to light vs deep verification paths."

    @staticmethod
    def _parse_enumerated(raw: Any, state: dict) -> list[dict]:
        """Parse enumeratedSources with multiple fallback strategies."""

        # If already a list, use it
        if isinstance(raw, list):
            return raw

        if not isinstance(raw, str) or not raw.strip():
            return []

        text = raw.strip()

        # Strategy 1: Direct JSON parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: Extract JSON from markdown fences ```json ... ```
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: Extract URLs from free-form text and build candidates
        urls = re.findall(r"https?://[^\s\"',\]>)]+", text)
        if urls:
            logger.info(
                f"[VerificationRouter] JSON parse failed, extracted {len(urls)} URLs from text"
            )
            # Try to match URLs to categories by keyword heuristics
            candidates = []
            used_urls = set()
            for cat, meta in MASTER_SOURCE_TAXONOMY.items():
                if meta.get("check") in ("api_call", "dma_lookup"):
                    continue
                # Look for a URL that might match this category
                keywords = cat.replace("_", " ").split()
                best_url = ""
                for url in urls:
                    url_lower = url.lower()
                    if any(kw in url_lower for kw in keywords) and url not in used_urls:
                        best_url = url
                        used_urls.add(url)
                        break
                if best_url:
                    candidates.append({
                        "category": cat,
                        "exists": True,
                        "searchEvidence": f"URL extracted from enumeration text",
                        "candidateUrl": best_url,
                    })
            if candidates:
                return candidates

        # Strategy 4 (ultimate fallback): No parseable output at all —
        # create candidates from MASTER_SOURCE_TAXONOMY for always_exists
        # and fill search_template URLs so deep verification can still run
        logger.warning(
            "[VerificationRouter] All parse strategies failed — "
            "falling back to taxonomy-based candidates"
        )
        return VerificationRouter._taxonomy_fallback_candidates(state)

    @staticmethod
    def _taxonomy_fallback_candidates(state: dict) -> list[dict]:
        """Build candidates from MASTER_SOURCE_TAXONOMY when enumeration fails entirely."""
        city = state.get("city", "unknown")
        st = state.get("state", "")
        county = state.get("county", "")
        city_slug = city.lower().replace(" ", "")
        state_slug = st.lower().replace(" ", "")

        candidates = []
        for cat, meta in MASTER_SOURCE_TAXONOMY.items():
            if meta.get("check") in ("api_call", "dma_lookup"):
                continue

            template = meta.get("search_template", "")
            query = (
                template.replace("{city}", city)
                .replace("{state}", st)
                .replace("{county}", county)
                .replace("{city_slug}", city_slug)
                .replace("{state_slug}", state_slug)
            )

            # always_exists categories are marked exists=True
            always = meta.get("always_exists", False)
            candidates.append({
                "category": cat,
                "exists": always or (cat in DEEP_VERIFICATION_CATEGORIES),
                "searchEvidence": f"Fallback from taxonomy — search: {query}",
                "candidateUrl": "",
            })
        return candidates

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        raw_enumerated = state.get("enumeratedSources", "")

        # Parse enumeratedSources with robust fallback strategies
        enumerated = self._parse_enumerated(raw_enumerated, dict(state))

        now = datetime.utcnow().isoformat()
        light_verified: dict[str, dict[str, Any]] = {}
        deep_candidates: list[dict[str, Any]] = []

        for item in enumerated:
            if not isinstance(item, dict):
                continue

            category = item.get("category", "")
            exists = item.get("exists", False)
            url = item.get("candidateUrl", "")
            evidence = item.get("searchEvidence", "")

            if not exists:
                # Not found — record as not_found in light_verified for assembly
                light_verified[category] = {
                    "status": "not_found",
                    "lastVerified": now,
                    "note": evidence,
                }
                continue

            if category in LIGHT_VERIFICATION_CATEGORIES:
                # Light verification: URL from enumeration is sufficient
                light_verified[category] = {
                    "status": "verified" if url else "not_found",
                    "url": url,
                    "active": True if url else None,
                    "lastVerified": now,
                    "note": evidence,
                }
            elif category in DEEP_VERIFICATION_CATEGORIES:
                # Deep verification needed
                deep_candidates.append({
                    "category": category,
                    "candidateUrl": url,
                    "searchEvidence": evidence,
                })
            else:
                # Unknown category — treat as light
                light_verified[category] = {
                    "status": "verified" if url else "not_found",
                    "url": url,
                    "lastVerified": now,
                    "note": evidence,
                }

        logger.info(
            f"[VerificationRouter] Split: {len(light_verified)} light, "
            f"{len(deep_candidates)} deep candidates"
        )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={
                "lightVerified": light_verified,
                "deepCandidates": deep_candidates,
            }),
        )


# ---------------------------------------------------------------------------
# Stage 4: Deep verification sub-agents (one per DEEP category)
# ---------------------------------------------------------------------------


def _verify_instruction(category_name: str):
    """Build a dynamic instruction function for a deep verifier sub-agent."""

    def builder(ctx) -> str:
        state = getattr(ctx, "state", {})
        candidates = state.get("deepCandidates", [])
        city = state.get("city", "unknown")
        st = state.get("state", "")
        meta = MASTER_SOURCE_TAXONOMY.get(category_name, {})

        # Find this category in candidates
        candidate = next(
            (c for c in candidates if c.get("category") == category_name),
            None,
        )
        if not candidate:
            return (
                f"No candidate found for category '{category_name}'. "
                f"Return JSON: {{\"category\": \"{category_name}\", \"status\": \"skipped\"}}"
            )

        subpages_hint = meta.get("subpages", [])
        subpages_text = ""
        if subpages_hint:
            subpages_text = f"\nLook for these subpages: {', '.join(subpages_hint)}"

        return f"""You are a source verification agent. Verify this data source for {city}, {st}:

Category: {candidate['category']}
Description: {meta.get('description', category_name)}
URL: {candidate.get('candidateUrl', '')}
Evidence: {candidate.get('searchEvidence', '')}
{subpages_text}

Navigate to the URL, verify it's active, and return a JSON object:
{{
  "category": "{category_name}",
  "status": "verified" or "not_found" or "pdf_only",
  "url": "the verified URL",
  "subpages": {{"subpage_name": "url"}},
  "active": true/false,
  "hasOnlinePortal": true/false,
  "accessType": "api" or "searchable_portal" or "pdf_only" or "none",
  "eventsUrl": "",
  "calendarUrl": "",
  "note": "any relevant observations"
}}

Rules:
- "verified" = real, active, usable page
- "not_found" = URL is dead, generic, or not actually for this source
- "pdf_only" = data exists but only as downloadable PDFs (not machine-readable)
- Only include subpages you actually found — don't guess
"""

    return builder


# ---------------------------------------------------------------------------
# Stage 5: ProfileAssembler (BaseAgent — deterministic, no LLM)
# ---------------------------------------------------------------------------


class ProfileAssembler(BaseAgent):
    """Merges all verification results into a ZipcodeProfile and saves to Firestore.

    Reads apiSources, lightVerified, and verified_* from state.
    Writes final profile to state via state_delta.
    """

    name: str = "ProfileAssembler"
    description: str = "Assembles final ZipcodeProfile from all verification stages."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        zip_code = state.get("zipCode", "")
        city = state.get("city", "")
        st = state.get("state", "")
        county = state.get("county", "")
        dma_name = state.get("dmaName", "")

        now = datetime.utcnow()
        all_sources: dict[str, dict[str, Any]] = {}

        # 1. Add API-checked sources
        api_sources = state.get("apiSources", {})
        for cat, entry in api_sources.items():
            all_sources[cat] = entry if isinstance(entry, dict) else {}

        # 2. Add light-verified sources
        light_verified = state.get("lightVerified", {})
        for cat, entry in light_verified.items():
            all_sources[cat] = entry if isinstance(entry, dict) else {}

        # 3. Add deep-verified sources from each verifier sub-agent
        for category_name in DEEP_VERIFICATION_CATEGORIES:
            key = f"verified_{category_name}"
            raw = state.get(key, "")

            if not raw:
                # Check if this category was in deepCandidates but verifier
                # returned nothing — mark not_found
                deep_candidates = state.get("deepCandidates", [])
                was_candidate = any(
                    c.get("category") == category_name
                    for c in deep_candidates
                    if isinstance(c, dict)
                )
                if was_candidate and category_name not in all_sources:
                    all_sources[category_name] = {
                        "status": "not_found",
                        "lastVerified": now.isoformat(),
                        "note": "Deep verification returned no result",
                    }
                continue

            # Parse the verifier output
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    parsed = {}
            elif isinstance(raw, dict):
                parsed = raw
            else:
                parsed = {}

            if parsed:
                status = parsed.get("status", "not_found")
                # Handle "skipped" status from verifiers with no candidate
                if status == "skipped":
                    continue
                all_sources[category_name] = {
                    "status": status,
                    "url": parsed.get("url", ""),
                    "lastVerified": now.isoformat(),
                    "subpages": parsed.get("subpages", {}),
                    "active": parsed.get("active"),
                    "hasOnlinePortal": parsed.get("hasOnlinePortal"),
                    "accessType": parsed.get("accessType", ""),
                    "eventsUrl": parsed.get("eventsUrl", ""),
                    "calendarUrl": parsed.get("calendarUrl", ""),
                    "note": parsed.get("note", ""),
                }

        # 4. Count confirmed vs unavailable
        confirmed_count = 0
        unavailable_count = 0
        unavailable_list: list[str] = []

        for cat, entry in all_sources.items():
            if entry.get("status") == "verified":
                confirmed_count += 1
            else:
                unavailable_count += 1
                label = f"{cat}: {entry.get('status', 'unknown')}"
                note = entry.get("note", "")
                if note:
                    label += f" ({note})"
                unavailable_list.append(label)

        # 5. Build profile dict (plain dicts, not Pydantic — for Firestore)
        # Strip None values from source entries
        clean_sources = {}
        for cat, entry in all_sources.items():
            clean_sources[cat] = {
                k: v for k, v in entry.items() if v is not None
            }

        profile_dict = {
            "zipCode": zip_code,
            "city": city,
            "state": st,
            "county": county,
            "dmaName": dma_name,
            "profileVersion": "2.0",
            "discoveredAt": now.isoformat(),
            "refreshAfter": (now + timedelta(days=90)).isoformat(),
            "enumeratedSources": len(all_sources),
            "confirmedSources": confirmed_count,
            "unavailableSources": unavailable_count,
            "sources": clean_sources,
            "unavailable": unavailable_list,
        }

        # 6. Save to Firestore
        try:
            from hephae_db.firestore.zipcode_profiles import save_zipcode_profile

            await save_zipcode_profile(profile_dict)
            logger.info(
                f"[ProfileAssembler] Saved profile for {zip_code}: "
                f"{confirmed_count} confirmed, {unavailable_count} unavailable"
            )
        except Exception as e:
            logger.error(f"[ProfileAssembler] Firestore save failed: {e}")

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"profileResult": profile_dict}),
        )


# ---------------------------------------------------------------------------
# Factory: create_discovery_agent()
# ---------------------------------------------------------------------------


def create_discovery_agent() -> SequentialAgent:
    """Create a fresh discovery agent tree (factory pattern).

    ADK agents can only have one parent, so we create fresh instances
    per invocation. Same pattern as create_pulse_orchestrator().
    """

    # -- Stage 1: APISourceChecker (BaseAgent, no LLM)
    api_checker = APISourceChecker()

    # -- Stage 2: SourceEnumerator (LlmAgent + google_search)
    source_enumerator = LlmAgent(
        name="SourceEnumerator",
        model=AgentModels.PRIMARY_MODEL,
        description="Searches for all non-API source categories via Google.",
        instruction=_enumerator_instruction,
        tools=[google_search],
        output_key="enumeratedSources",
        on_model_error_callback=fallback_on_error,
    )

    # -- Stage 3: VerificationRouter (BaseAgent, no LLM)
    verification_router = VerificationRouter()

    # -- Stage 4: Deep verification split into crawl vs search-only
    # CrawlVerifierFanOut: 5 categories that need crawl4ai (google_search + crawl4ai)
    # SearchVerifierFanOut: 7 categories with google_search only (no crawl4ai)
    crawl_verifier_agents = []
    for category_name in sorted(CRAWL_DEEP_CATEGORIES):
        agent = LlmAgent(
            name=f"DeepVerify_{category_name}",
            model=AgentModels.PRIMARY_MODEL,
            description=f"Verifies {category_name} source via crawl.",
            instruction=_verify_instruction(category_name),
            tools=[google_search_tool, crawl4ai_advanced_tool],
            output_key=f"verified_{category_name}",
            max_llm_calls=5,
            on_model_error_callback=fallback_on_error,
        )
        crawl_verifier_agents.append(agent)

    search_verifier_agents = []
    for category_name in sorted(SEARCH_ONLY_DEEP_CATEGORIES):
        agent = LlmAgent(
            name=f"DeepVerify_{category_name}",
            model=AgentModels.PRIMARY_MODEL,
            description=f"Verifies {category_name} source via search.",
            instruction=_verify_instruction(category_name),
            tools=[google_search_tool],
            output_key=f"verified_{category_name}",
            max_llm_calls=3,
            on_model_error_callback=fallback_on_error,
        )
        search_verifier_agents.append(agent)

    crawl_verifier_fan_out = ParallelAgent(
        name="CrawlVerifierFanOut",
        sub_agents=crawl_verifier_agents,
    )
    search_verifier_fan_out = ParallelAgent(
        name="SearchVerifierFanOut",
        sub_agents=search_verifier_agents,
    )

    # -- Stage 5: ProfileAssembler (BaseAgent, no LLM)
    assembler = ProfileAssembler()

    # -- Wire all stages sequentially
    # Stage 4 is split: crawl-based verifiers run first, then search-only verifiers
    return SequentialAgent(
        name="ZipcodeProfileDiscovery",
        description="5-stage zipcode profile discovery pipeline.",
        sub_agents=[
            api_checker,
            source_enumerator,
            verification_router,
            crawl_verifier_fan_out,
            search_verifier_fan_out,
            assembler,
        ],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_zipcode_profile_discovery(zip_code: str) -> dict[str, Any]:
    """Run full discovery for a zip code via ADK agent tree and save the profile.

    1. Resolve geography
    2. Build initial state
    3. Run create_discovery_agent() via Runner + InMemorySessionService
    4. Extract profile from final session state
    5. Return profile dict

    Returns the profile dict (already saved to Firestore by ProfileAssembler).
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

    # Resolve DMA using deterministic STATE_TO_DMA map
    dma_name = STATE_TO_DMA.get(state, "")

    logger.info(
        f"[ProfileDiscovery] Geography: {city}, {state} ({county} County), "
        f"DMA: {dma_name or 'N/A'}"
    )

    # Step 2: Spin up 5 ephemeral crawl4ai instances (one per crawl-required verifier)
    import os
    from hephae_api.lib.crawl4ai.ephemeral import create_ephemeral_crawl4ai, destroy_ephemeral_crawl4ai

    ephemeral_names: list[str] = []
    ephemeral_url: str | None = None
    original_crawl4ai_url = os.environ.get("CRAWL4AI_URL", "")

    NUM_CRAWLERS = 5
    logger.info(f"[ProfileDiscovery] Spinning up {NUM_CRAWLERS} ephemeral crawl4ai instances")

    # Spin up crawlers — use the first one that succeeds as the primary URL
    # Cloud Run auto-scales, so one service with max-instances=5 is better than 5 services
    ephemeral_name = f"disc-{zip_code}"
    try:
        ephemeral_url = await create_ephemeral_crawl4ai(ephemeral_name)
        if ephemeral_url:
            ephemeral_names.append(ephemeral_name)
            logger.info(f"[ProfileDiscovery] Ephemeral crawl4ai ready: {ephemeral_url}")
        else:
            raise RuntimeError("create_ephemeral_crawl4ai returned None")
    except Exception as e:
        logger.error(f"[ProfileDiscovery] FAILED to create ephemeral crawl4ai: {e}")
        raise RuntimeError(
            f"Discovery requires ephemeral crawl4ai but failed to create: {e}. "
            f"Check Cloud Run permissions and crawl4ai image availability."
        )

    # Override the module-level CRAWL4AI_URL so the tool uses our ephemeral instance
    os.environ["CRAWL4AI_URL"] = ephemeral_url
    # Also reload the module-level variable in the crawl4ai tool
    try:
        import hephae_agents.shared_tools.crawl4ai as crawl4ai_mod
        crawl4ai_mod.CRAWL4AI_URL = ephemeral_url
        logger.info(f"[ProfileDiscovery] Overrode CRAWL4AI_URL → {ephemeral_url}")
    except Exception as e:
        logger.warning(f"[ProfileDiscovery] Could not override crawl4ai module URL: {e}")

    # Step 3: Build initial session state
    initial_state = {
        "zipCode": zip_code,
        "city": city,
        "state": state,
        "county": county,
        "latitude": latitude,
        "longitude": longitude,
        "dmaName": dma_name,
        "crawl4aiUrl": ephemeral_url,
    }

    # Step 4: Run ADK agent tree (wrapped in try/finally for cleanup)
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from hephae_common.adk_helpers import user_msg

    profile = None
    try:
        orchestrator = create_discovery_agent()
        session_service = InMemorySessionService()
        runner = Runner(
            agent=orchestrator,
            app_name="zipcode_profile_discovery",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="zipcode_profile_discovery",
            user_id="system",
            state=initial_state,
        )

        logger.info(f"[ProfileDiscovery] Running ADK pipeline for {zip_code}")
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=user_msg(
                f"Discover data sources for zip code {zip_code} ({city}, {state})."
            ),
        ):
            pass  # Pipeline runs through all stages

        # Re-fetch session to get final state
        session = await session_service.get_session(
            app_name="zipcode_profile_discovery",
            user_id="system",
            session_id=session.id,
        )
        final_state = dict(session.state or {})
        logger.info(
            f"[ProfileDiscovery] Pipeline complete — state keys: {list(final_state.keys())}"
        )

        # Extract profile from state
        profile = final_state.get("profileResult")

    finally:
        # Step 5: ALWAYS restore original CRAWL4AI_URL and destroy ephemeral instances
        os.environ["CRAWL4AI_URL"] = original_crawl4ai_url
        try:
            import hephae_agents.shared_tools.crawl4ai as crawl4ai_mod
            crawl4ai_mod.CRAWL4AI_URL = original_crawl4ai_url
        except Exception:
            pass

        for ename in ephemeral_names:
            try:
                await destroy_ephemeral_crawl4ai(ename)
                logger.info(f"[ProfileDiscovery] Destroyed ephemeral crawl4ai: {ename}")
            except Exception as e:
                logger.warning(f"[ProfileDiscovery] Cleanup failed for {ename}: {e}")

    # Step 6: Extract profile from state
    # (profile was set in the try block above)

    if not profile or not isinstance(profile, dict):
        logger.error("[ProfileDiscovery] No profileResult in final state")
        return {"error": "Discovery pipeline produced no result"}

    confirmed = profile.get("confirmedSources", 0)
    unavailable = profile.get("unavailableSources", 0)
    total = profile.get("enumeratedSources", 0)

    logger.info(
        f"[ProfileDiscovery] Complete for {zip_code}: "
        f"{confirmed} confirmed, {unavailable} unavailable (out of {total} total)"
    )

    return profile
