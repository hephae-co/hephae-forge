# CLAUDE.md — Hephae Forge Monorepo

This is the root of the hephae-forge monorepo. It contains three services, shared libraries, AI agents, and centralized tests.

## Repository Structure

```
hephae-forge/
├── apps/
│   ├── web/                   # Customer-facing web app (hephae.co) — Next.js 16 frontend
│   ├── admin/                 # Internal admin dashboard — Next.js 14.1 frontend
│   └── api/                   # Unified backend API — FastAPI (serves both UIs)
│       └── hephae_api/        # API module (routers, workflows, config)
├── agents/                    # hephae-agents — All AI agents + stateless runner functions
│   └── hephae_agents/
├── lib/
│   ├── common/                # hephae-common — Models, config, auth, Firebase, helpers
│   │   └── hephae_common/
│   ├── db/                    # hephae-db — All Firestore, BigQuery, GCS access
│   │   └── hephae_db/
│   ├── integrations/          # hephae-integrations — 3rd-party API clients (BLS, USDA, etc.)
│   │   └── hephae_integrations/
│   └── common-ts/             # @hephae/common — Shared TypeScript types
├── tests/                     # Centralized test suite (capabilities, workflows, API, integration)
├── infra/                     # Infrastructure, deploy scripts, contracts
│   ├── docker/                # Dockerfiles
│   ├── scripts/               # Deploy scripts (deploy.sh, trigger-evals.sh, etc.)
│   ├── contracts/             # Shared API & data contracts (documentation)
│   └── setup.sh               # GCP project bootstrap
└── package.json               # npm workspaces root
```

## Services (Cloud Run deployments)

| Service | Stack | Port | Purpose |
|---------|-------|------|---------|
| `apps/web/` | Next.js 16 | 3000 | Customer UI — proxies `/api/*` to unified API |
| `apps/admin/` | Next.js 14.1 | 3000 | Admin UI — proxies `/api/*` to unified API |
| `apps/api/` | FastAPI | 8080 | Unified backend — all capabilities, workflows, DB access |

Both UIs call the same API. Capabilities are direct Python imports (no inter-service HTTP).

## Shared Packages

| Package | Name | Contains |
|---------|------|----------|
| `lib/common/` | `hephae-common` | Models, config, auth, Firebase, model fallback, ADK helpers, email, report templates |
| `lib/common-ts/` | `@hephae/common` | TypeScript types |
| `lib/db/` | `hephae-db` | Firestore, BigQuery, GCS, BusinessContext |
| `lib/integrations/` | `hephae-integrations` | BLS, USDA, FDA, OSM, social media API clients |
| `agents/` | `hephae-agents` | All AI agents + runner.py files (stateless: identity → report) |

### Dependency Graph (no cycles)
```
apps/api              → hephae-agents, hephae-db, hephae-integrations, hephae-common
hephae-agents         → hephae-integrations, hephae-db, hephae-common
hephae-integrations   → hephae-common
hephae-db             → hephae-common
hephae-common         → (external only)
```

## Cross-App Standards

### Model Strategy

All AI agents use Google Gemini via Google ADK.

| Tier | Model | Use Case |
|------|-------|----------|
| PRIMARY | `gemini-3.1-flash-lite-preview` | All standard agents (discovery, research, formatting, outreach) |
| PRIMARY_FALLBACK | `gemini-2.5-flash-lite` | Automatic fallback on 429/503/529 |
| ENHANCED | `gemini-3.0-flash-preview` | Complex analysis (SEO auditor) |
| CREATIVE_VISION | `gemini-3-pro-image-preview` | Image generation |

Thinking modes: MEDIUM for evaluators, HIGH for competitive/market positioning.

Model tiers are defined in `lib/common/hephae_common/model_config.py`.

### Database Rules (strictly enforced)

1. **No blobs in Firestore or BigQuery** — upload binary assets to GCS (CDN bucket `hephae-co-dev-prod-cdn-assets` for reports/cards, legacy `everything-hephae` for menus), store only the resulting URL.
2. **`zipCode` is first-class** — always a top-level field, never derived from address at query time.
3. **No growing arrays in Firestore** — no `reports[]`, no `analyses[]`. Historical data goes to BigQuery. Firestore stores only current state.
4. **Use `update()` with dotted paths** for nested Firestore fields. `set({merge:true})` only for new docs.

### Agent Versioning

Every agent has a semantic version in `apps/api/hephae_api/config.py` under `AgentVersions`.

- MAJOR: output schema change (fields added/removed/renamed)
- MINOR: logic change, same schema
- PATCH: prompt wording, no logic change

Bump the version in the same commit as the breaking change.

### Authentication

| Context | Mechanism |
|---------|-----------|
| UI → API | HMAC-SHA256 signing (`FORGE_API_SECRET`) or API key header |
| Cloud Run services | GCP identity tokens via metadata server |
| Firestore rules | All client access denied (`allow read, write: if false`) |

Note: Inter-service auth (admin→web HMAC) has been eliminated — capabilities are direct Python imports within the unified API.

### GCP Infrastructure

All services deploy to `us-central1`. Run `bash infra/setup.sh` to bootstrap a fresh project.

| Component | Value |
|-----------|-------|
| Region | `us-central1` (all services, builds, jobs) |
| GCP Project | Set via `GCP_PROJECT_ID` env var |
| Firestore | Default (auto-initialized via ADC) |
| BigQuery Dataset | `$GCP_PROJECT_ID.hephae` |
| GCS Bucket (legacy) | Set via `GCS_BUCKET` env var |
| GCS CDN Bucket | Set via `GCS_CDN_BUCKET` env var |
| CDN Public Base | Set via `CDN_BASE_URL` env var |

### Evaluation Standards

Evaluator agents validate capability outputs:
- **Pass threshold:** score >= 80 AND !isHallucinated
- **Evaluator model:** ENHANCED tier + MEDIUM thinking
- All 4 capabilities (SEO, traffic, competitive, margin) have dedicated evaluator agents in `agents/hephae_agents/evaluators/`

## Contracts

See `infra/contracts/` for shared documentation:
- `infra/contracts/firestore-schema.md` — Firestore document shapes
- `infra/contracts/bigquery-schema.md` — BigQuery table definitions
- `infra/contracts/api-web.md` — Web-facing API routes
- `infra/contracts/api-admin.md` — Admin-facing API routes
- `infra/contracts/gcs-conventions.md` — GCS path patterns
- `infra/contracts/eval-standards.md` — Evaluation criteria and thresholds

## Commands

```bash
# First-time GCP setup (idempotent — safe to re-run)
bash infra/setup.sh

# Unified API
cd apps/api && pip install -e . && uvicorn hephae_api.main:app --reload --port 8080

# Web UI
cd apps/web && npm install && npm run dev

# Admin UI
cd apps/admin && npm install && npm run dev

# Install all shared packages
pip install -e lib/common -e lib/db -e lib/integrations -e agents

# Run tests
python -m pytest tests/

# Deploy (all to us-central1)
bash infra/scripts/deploy.sh              # Unified API
bash apps/web/infra/deploy.sh       # Web frontend
bash apps/admin/infra/deploy.sh     # Admin frontend
```

## Working in This Repo

- When modifying shared packages, run tests across all consumers.
- When changing an API endpoint, update the corresponding `infra/contracts/` doc.
- Each app has its own `CLAUDE.md` with app-specific details. Read it before working in that app.
- Agents are in `agents/` — each has a `runner.py` (stateless: identity in, report out).
- DB access is in `lib/db/` — never access Firestore/BQ directly from routers or agents.
