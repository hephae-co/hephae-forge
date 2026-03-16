# System Overview

> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

## Service Topology

Hephae Forge is a monorepo with three Cloud Run services and four shared Python packages.

```
┌──────────────────┐     ┌──────────────────┐
│   apps/web/      │     │   apps/admin/    │
│   Next.js 16     │     │   Next.js 14.1   │
│   Port 3000      │     │   Port 3000      │
│   (hephae.co)    │     │   (admin UI)     │
└────────┬─────────┘     └────────┬─────────┘
         │  /api/*                │  /api/*
         │  (proxy)               │  (proxy)
         └────────────┬───────────┘
                      ▼
         ┌────────────────────────┐
         │   apps/api/            │
         │   FastAPI (Python)     │
         │   Port 8080            │
         │   Unified Backend API  │
         └────────────────────────┘
              │          │
    ┌─────────┤          ├──────────┐
    ▼         ▼          ▼          ▼
Firestore  BigQuery    GCS     Gemini API
```

Both UIs call the same API. Capabilities are **direct Python imports** — no inter-service HTTP.

## Services

| Service | Stack | Port | Cloud Run Service | Purpose |
|---------|-------|------|-------------------|---------|
| `apps/web/` | Next.js 16 (React 19) | 3000 | `hephae-co-site` | Customer UI — proxies `/api/*` to unified API |
| `apps/admin/` | Next.js 14.1 (App Router) | 3000 | `hephae-admin-web` | Admin dashboard — proxies `/api/*` to unified API |
| `apps/api/` | FastAPI + Python | 8080 | `hephae-forge-api` | Unified backend — all capabilities, workflows, DB access |

## Package Dependency Graph

```
apps/api
  └── hephae-agents  (agents/)
        └── hephae-integrations  (lib/integrations/)
        │     └── hephae-common  (lib/common/)
        └── hephae-db  (lib/db/)
        │     └── hephae-common
        └── hephae-common
```

**No dependency cycles.** `hephae-common` is the leaf — it depends only on external packages.

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
| PRIMARY | `AgentModels.PRIMARY_MODEL` | `gemini-3.1-flash-lite-preview` | All agents — default |
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
| UI → API | HMAC-SHA256 signing | `FORGE_API_SECRET` |
| Legacy v1 endpoints | API key header | `FORGE_V1_API_KEY` |
| Cron / Cloud Tasks | Bearer token | `CRON_SECRET` |
| Cloud Run → Cloud Run | GCP identity tokens | Auto (metadata server) |
| Firestore rules | All client access denied | `allow read, write: if false` |
| Admin email allowlist | Comma-separated emails | `ADMIN_EMAIL_ALLOWLIST` |

## Database Rules

1. **No blobs in Firestore or BigQuery** — upload to GCS, store only the URL
2. **`zipCode` is first-class** — always a top-level field, never derived from address
3. **No growing arrays** — no `reports[]`, no `analyses[]`. Historical data goes to BigQuery.
4. **Use `update()` with dotted paths** for nested Firestore fields. `set({merge:true})` only for new docs.

## API Structure

The unified API at `apps/api/` serves all routes under `/api/`:

| Router Group | Count | Purpose |
|-------------|-------|---------|
| Web routers | 12 | Customer-facing (auth, chat, discover, analyze, capabilities, blog, social, etc.) |
| Admin routers | 15 | Workflow CRUD, research, testing, stats, tasks, content |
| V1 routers | 5 | Legacy backward-compat (discover, analyze, seo, competitive, traffic) |
| Batch/Cron routers | 5 | Cron jobs, workflow monitoring, batch dispatch |

**Middleware:**

- **CORS** — Origins from `ALLOWED_ORIGINS` env var (default: `*`)
- **TraceMiddleware** — Assigns `trace_id` per request (from `x-request-id` header or uuid4). All logs include trace ID for correlation.

**Source:** `apps/api/hephae_api/main.py`

## Agent Versioning

Every agent has a semantic version in `apps/api/hephae_api/config.py` under `AgentVersions`:

- **MAJOR** — output schema change (fields added/removed/renamed)
- **MINOR** — logic change, same schema
- **PATCH** — prompt wording, no logic change

Bump the version in the same commit as the breaking change.

## Key Architectural Patterns

| Pattern | Description |
|---------|-------------|
| No inter-service HTTP | Capabilities are direct Python imports, not HTTP calls |
| Stateless agents | Every agent: `runner.py` takes identity dict → returns report dict |
| Capability registry | Maps capability names to runner functions + evaluators |
| SSE streaming | Starlette `StreamingResponse` for real-time workflow progress |
| Request correlation | `trace_id` injected into all log records via middleware |
| Firebase auto-init | Initialized once on API startup via lifespan handler |

## Source Files

| Area | File |
|------|------|
| Monorepo config | `CLAUDE.md` |
| API entry point | `apps/api/hephae_api/main.py` |
| API config / env vars | `apps/api/hephae_api/config.py` |
| Model tiers | `lib/common/hephae_common/model_config.py` |
| Model fallback | `lib/common/hephae_common/model_fallback.py` |
| Agent versions | `apps/api/hephae_api/config.py` → `AgentVersions` |
