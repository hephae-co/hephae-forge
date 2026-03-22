> Auto-generated from codebase on 2026-03-22.

# System Overview

## Service Topology

Hephae Forge is a monorepo with three Cloud Run services and four shared Python packages.

```
+-----------------+     +-----------------+
|   apps/web/     |     |   apps/admin/   |
|   Next.js 16    |     |   Next.js 14.1  |
|   Port 3000     |     |   Port 3000     |
|   (hephae.co)   |     |   (admin UI)    |
+--------+--------+     +--------+--------+
         |  /api/*                |  /api/*
         |  (proxy)               |  (proxy)
         +-----------+------------+
                     v
         +-----------------------+
         |   apps/api/           |
         |   FastAPI (Python)    |
         |   Port 8080           |
         |   Unified Backend API |
         +-----------+-----------+
              |          |
    +---------+          +---------+
    v         v          v         v
Firestore  BigQuery    GCS     Gemini API
```

Both UIs call the same API. Capabilities are **direct Python imports** -- no inter-service HTTP.

## Services

| Service | Stack | Port | Cloud Run Name | Purpose |
|---------|-------|------|----------------|---------|
| `apps/web/` | Next.js 16 (React 19) | 3000 | `hephae-forge-web` | Customer UI -- proxies `/api/*` to unified API |
| `apps/admin/` | Next.js 14.1 (App Router) | 3000 | `hephae-admin-web` | Admin dashboard -- proxies `/api/*` to unified API |
| `apps/api/` | FastAPI + Python | 8080 | `hephae-forge-api` | Unified backend -- all capabilities, workflows, DB access |

## Package Dependency Graph

```
apps/api
  +-- hephae-agents  (agents/)
  |     +-- hephae-integrations  (lib/integrations/)
  |     |     +-- hephae-common  (lib/common/)
  |     +-- hephae-db  (lib/db/)
  |     |     +-- hephae-common
  |     +-- hephae-common
```

**No dependency cycles.** `hephae-common` is the leaf -- it depends only on external packages.

| Package | Path | Contains |
|---------|------|----------|
| `hephae-common` | `lib/common/` | Models, config, auth, Firebase, model fallback, ADK helpers, email, report templates |
| `hephae-db` | `lib/db/` | Firestore, BigQuery, GCS access layer |
| `hephae-integrations` | `lib/integrations/` | 3rd-party API clients (BLS, USDA, FDA, OSM, social media) |
| `hephae-agents` | `agents/` | All AI agents + stateless runner functions |
| `@hephae/common` | `lib/common-ts/` | Shared TypeScript types for UIs |

## AI Model Strategy

All agents use Google Gemini via Google ADK.

| Tier | Constant | Model ID | Use Case |
|------|----------|----------|----------|
| PRIMARY | `AgentModels.PRIMARY_MODEL` | `gemini-3.1-flash-lite-preview` | All agents -- default |
| SYNTHESIS | `AgentModels.SYNTHESIS_MODEL` | `gemini-3-flash-preview` | Higher-quality model for final synthesis stage |
| FALLBACK | `AgentModels.FALLBACK_MODEL` | `gemini-3-flash-preview` | Auto-fallback on 429/503/529 |
| CREATIVE_VISION | `AgentModels.CREATIVE_VISION_MODEL` | `gemini-3.1-flash-image-preview` | Image generation |

**Thinking Presets:**

| Preset | Config | Used By |
|--------|--------|---------|
| MEDIUM | `thinking_level="MEDIUM"` | Evaluators |
| HIGH | `thinking_level="HIGH"` | Competitive analysis, market positioning |
| DEEP | `thinking_budget=8192` | Complex analysis (SEO, research, blog) |

**Fallback Logic:** When the primary model returns 429/503/529, the system automatically retries with `gemini-3-flash-preview`. Defined in `lib/common/hephae_common/model_fallback.py`.

## Authentication

| Context | Mechanism | Env Var |
|---------|-----------|---------|
| UI -> API | HMAC-SHA256 signing | `FORGE_API_SECRET` |
| Legacy v1 endpoints | API key header | `FORGE_V1_API_KEY` |
| Cron / Cloud Tasks | Bearer token | `CRON_SECRET` |
| Cloud Run -> Cloud Run | GCP identity tokens | Auto (metadata server) |
| Firestore rules | All client access denied | `allow read, write: if false` |
| Admin email allowlist | Comma-separated emails | `ADMIN_EMAIL_ALLOWLIST` |

## Database Rules

1. **No blobs in Firestore or BigQuery** -- upload to GCS, store only the URL
2. **`zipCode` is first-class** -- always a top-level field, never derived from address
3. **No growing arrays** -- no `reports[]`, no `analyses[]`. Historical data goes to BigQuery.
4. **Use `update()` with dotted paths** for nested Firestore fields. `set({merge:true})` only for new docs.

## API Structure

The unified API at `apps/api/` serves all routes under `/api/`:

| Router Group | Count | Purpose |
|-------------|-------|---------|
| Web routers | 14 | Customer-facing (auth, chat, discover, analyze, capabilities, blog, social, heartbeat, overview, profile builder, etc.) |
| Admin routers | 21 | Workflow CRUD, research, testing, stats, tasks, content, pulse, registered zipcodes/industries |
| V1 routers | 5 | Legacy backward-compat (discover, analyze, seo, competitive, traffic) |
| Batch/Cron routers | 8 | Cron jobs, workflow monitoring, batch dispatch, pulse cron, industry pulse cron |

**Middleware:**

- **CORS** -- Origins from `ALLOWED_ORIGINS` env var (default: `*`)
- **TraceMiddleware** -- Assigns `trace_id` per request (from `x-request-id` header or uuid4). All logs include trace ID for correlation.

**Source:** `apps/api/hephae_api/main.py`

## Agent Versioning

Every agent has a semantic version in `apps/api/hephae_api/config.py` under `AgentVersions`:

- **MAJOR** -- output schema change (fields added/removed/renamed)
- **MINOR** -- logic change, same schema
- **PATCH** -- prompt wording, no logic change

Current agent versions (as of 2026-03-22):

| Agent | Version | Notes |
|-------|---------|-------|
| DISCOVERY_PIPELINE | 5.1.0 | Parallel local context fetch, enhanced MenuAgent delivery search |
| SITE_CRAWLER | 1.1.0 | |
| CONTACT_DISCOVERY | 1.0.0 | |
| CONTACT_AGENT | 2.0.0 | emailStatus, contactFormUrl fields |
| QUALITY_GATE_AGENT | 1.0.1 | |
| MENU_DISCOVERY | 3.0.0 | DoorDash/Grubhub/UberEats platform search |
| SOCIAL_DISCOVERY | 2.0.0 | |
| SOCIAL_PROFILER | 2.0.0 | |
| MAPS_DISCOVERY | 2.0.0 | |
| COMPETITOR_DISCOVERY | 2.0.0 | |
| THEME_DISCOVERY | 2.0.0 | |
| BUSINESS_OVERVIEW | 1.0.0 | |
| MARGIN_SURGEON | 1.1.0 | PDF extraction, menuNotFound flow |
| SEO_AUDITOR | 1.1.0 | PRIMARY_MODEL + DEEP thinking |
| TRAFFIC_FORECASTER | 1.0.0 | |
| COMPETITIVE_ANALYZER | 1.0.0 | |
| MARKETING_SWARM | 1.0.0 | |
| SOCIAL_MEDIA_AUDITOR | 1.0.0 | |
| SOCIAL_POST_GENERATOR | 3.0.0 | CDN report links + social card images |
| BLOG_WRITER | 1.1.0 | PRIMARY_MODEL + DEEP thinking |
| LOCAL_CATALYST | 1.1.0 | PRIMARY_MODEL + DEEP thinking |
| DEMOGRAPHIC_EXPERT | 1.1.0 | PRIMARY_MODEL + DEEP thinking |
| WEEKLY_PULSE | 1.0.0 | |
| QUALIFICATION_SCANNER | 1.0.0 | |
| NEWS_DISCOVERY | 1.0.0 | |
| DISCOVERY_REVIEWER | 1.0.0 | |

Bump the version in the same commit as the breaking change.

## Two-Layer Pulse Architecture (NEW)

The weekly pulse system operates in two layers to avoid redundant national data fetching:

```
Layer 1: Industry Pulse (Sunday 3 AM ET)
+----------------------------------------+
| For each registered industry:          |
|   1. Fetch BLS CPI series             |
|   2. Fetch USDA commodity prices      |
|   3. Fetch FDA recalls                |
|   4. Compute impact multipliers       |
|   5. Match industry playbooks         |
|   6. Generate LLM trend summary       |
|   7. Save to industry_pulses          |
+----------------------------------------+
         |
         | Pre-computed national data
         v
Layer 2: Zip-Level Pulse (Monday 6 AM ET)
+----------------------------------------+
| For each registered zip x businessType:|
|   1. Load industry pulse (cache hit)   |
|   2. Fetch local signals (weather,     |
|      events, news, social)             |
|   3. Merge national + local signals    |
|   4. LLM synthesis                     |
|   5. Critique agent review             |
|   6. Save to weekly_pulses             |
+----------------------------------------+
```

### Registered Industry Configs

Three industry verticals are currently defined in `apps/api/hephae_api/workflows/orchestrators/industries.py`:

| ID | Name | BLS Series | USDA Commodities | Playbooks | Key Metrics |
|----|------|-----------|-----------------|-----------|-------------|
| `restaurant` | Restaurants & Cafes | 20 series (food CPI, proteins, dairy, produce) | CATTLE, HOGS, CHICKENS, EGGS, MILK, WHEAT | 3 (dairy_margin_swap, fda_recall_alert, weather_rain_prep) | Net margin 3-9% |
| `bakery` | Bakeries & Patisseries | 11 series (flour, eggs, butter, sugar, bakery products CPI) | WHEAT, EGGS, MILK, SUGAR | 6 (flour_cost_alert, egg_spike_response, butter_margin_squeeze, wedding_season_lock, holiday_pre_order_push, fda_allergen_alert) | Net margin 4-15%, ingredients 20-35% of revenue |
| `barber` | Barber Shops & Men's Grooming | 6 series (barber services CPI, rent, energy, services) | None (non-food) | 6 (service_price_cover, rent_squeeze_response, walk_in_weather_boost, event_upsell, slow_season_fill, new_competitor_alert) | Net margin 10-20%, labor 40-60% |

Each `IndustryConfig` is a frozen dataclass containing:
- `bls_series` -- BLS CPI series IDs to fetch (e.g. `"CUUR0000SAF1"` for Food CPI)
- `usda_commodities` -- USDA commodity keys (food verticals only)
- `track_labels` -- CPI label substrings mapped to named impact variables
- `playbooks` -- Conditional playbooks with trigger expressions and actionable plays
- `economist_context` / `scout_context` / `synthesis_context` -- Prompt context for LLM agents
- `critique_persona` -- Persona for the critique agent
- `social_search_terms` -- Keywords for social media signal search

Industry resolution uses alias matching with fuzzy substring fallback. Unknown types fall back to RESTAURANT.

**Source:** `apps/api/hephae_api/workflows/orchestrators/industries.py`

### Industry Pulse Orchestrator

The `generate_industry_pulse()` function in `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py`:

1. Checks Firestore cache (`industry_pulses` collection) -- skips if pulse exists for this week
2. Resolves the `IndustryConfig` for the given key
3. Fetches national signals via `fetch_national_signals()`
4. Computes impact multipliers via `compute_impact_multipliers()`
5. Matches playbooks via `match_playbooks()`
6. Generates a 2-3 paragraph LLM trend summary (PRIMARY_MODEL, no thinking preset)
7. Saves to Firestore and returns the pulse dict

## Key Architectural Patterns

| Pattern | Description |
|---------|-------------|
| No inter-service HTTP | Capabilities are direct Python imports, not HTTP calls |
| Stateless agents | Every agent: `runner.py` takes identity dict, returns report dict |
| Capability registry | Maps capability names to runner functions + evaluators |
| SSE streaming | Starlette `StreamingResponse` for real-time workflow progress |
| Request correlation | `trace_id` injected into all log records via middleware |
| Firebase auto-init | Initialized once on API startup via lifespan handler |
| Two-layer pulse | National industry pulse pre-computed Sunday, zip pulses Monday consume cached data |
| Industry configs as frozen dataclasses | Pure data, no methods -- adding a vertical means adding a new instance |

## Source Files

| Area | File |
|------|------|
| Monorepo config | `CLAUDE.md` |
| API entry point | `apps/api/hephae_api/main.py` |
| API config / env vars | `apps/api/hephae_api/config.py` |
| Model tiers | `lib/common/hephae_common/model_config.py` |
| Model fallback | `lib/common/hephae_common/model_fallback.py` |
| Agent versions | `apps/api/hephae_api/config.py` -> `AgentVersions` |
| Industry configs | `apps/api/hephae_api/workflows/orchestrators/industries.py` |
| Industry pulse orchestrator | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| Registered industries DB | `lib/db/hephae_db/firestore/registered_industries.py` |
| Industry pulse DB | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Industry pulse cron | `apps/api/hephae_api/routers/batch/industry_pulse_cron.py` |
| Registered industries admin | `apps/api/hephae_api/routers/admin/registered_industries.py` |
