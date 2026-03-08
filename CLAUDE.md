# CLAUDE.md — Hephae Forge Monorepo

This is the root of the hephae-forge monorepo. It contains three services, five shared packages, and centralized tests.

## Repository Structure

```
hephae-forge/
├── apps/
│   ├── web/                   # Customer-facing web app (hephae.co) — Next.js 16 frontend
│   ├── admin/                 # Internal admin dashboard — Next.js 14.1 frontend
│   └── api/                   # Unified backend API — FastAPI (serves both UIs)
├── packages/
│   ├── common-python/         # hephae-common — Models, config, auth, Firebase, helpers
│   ├── common-ts/             # @hephae/common — Shared TypeScript types
│   ├── db/                    # hephae-db — All Firestore, BigQuery, GCS access
│   ├── integrations/          # hephae-integrations — 3rd-party API clients (BLS, USDA, etc.)
│   └── capabilities/          # hephae-capabilities — All AI agents + stateless runner functions
├── tests/                     # Centralized test suite (capabilities, workflows, API, integration)
├── contracts/                 # Shared API & data contracts (documentation)
└── package.json               # npm workspaces root
```

## Services (Cloud Run deployments)

| Service | Stack | Port | Purpose |
|---------|-------|------|---------|
| `apps/web/` | Next.js 16 | 3000 | Customer UI — proxies `/api/*` to unified API |
| `apps/admin/` | Next.js 14.1 | 3000 | Admin UI — proxies `/api/*` to unified API |
| `apps/api/` | FastAPI | 8080 | Unified backend — all capabilities, workflows, DB access |

Both UIs call the same backend. Capabilities are direct Python imports (no inter-service HTTP).

## Shared Packages

| Package | Name | Contains |
|---------|------|----------|
| `packages/common-python/` | `hephae-common` | Models, config, auth, Firebase, model fallback, ADK helpers, email, report templates |
| `packages/common-ts/` | `@hephae/common` | TypeScript types |
| `packages/db/` | `hephae-db` | Firestore, BigQuery, GCS, BusinessContext |
| `packages/integrations/` | `hephae-integrations` | BLS, USDA, FDA, OSM, social media API clients |
| `packages/capabilities/` | `hephae-capabilities` | All AI agents + runner.py files (stateless: identity → report) |

### Dependency Graph (no cycles)
```
apps/api              → hephae-capabilities, hephae-db, hephae-integrations, hephae-common
hephae-capabilities   → hephae-integrations, hephae-db, hephae-common
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

Model tiers are defined in `packages/common-python/hephae_common/model_config.py`.

### Database Rules (strictly enforced)

1. **No blobs in Firestore or BigQuery** — upload binary assets to GCS (`everything-hephae` bucket), store only the resulting URL.
2. **`zipCode` is first-class** — always a top-level field, never derived from address at query time.
3. **No growing arrays in Firestore** — no `reports[]`, no `analyses[]`. Historical data goes to BigQuery. Firestore stores only current state.
4. **Use `update()` with dotted paths** for nested Firestore fields. `set({merge:true})` only for new docs.

### Agent Versioning

Every agent has a semantic version in `apps/api/backend/config.py` under `AgentVersions`.

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

| Component | Value |
|-----------|-------|
| GCP Project | `hephae-co-dev` |
| Firestore | Default (auto-initialized via ADC) |
| BigQuery Dataset | `hephae-co-dev.hephae` |
| GCS Bucket | `everything-hephae` |
| GCS Public Base | `https://storage.googleapis.com/everything-hephae/` |

### Evaluation Standards

Evaluator agents validate capability outputs:
- **Pass threshold:** score >= 80 AND !isHallucinated
- **Evaluator model:** ENHANCED tier + MEDIUM thinking
- All 4 capabilities (SEO, traffic, competitive, margin) have dedicated evaluator agents in `apps/api/backend/workflows/agents/evaluators/`

## Contracts

See `contracts/` for shared documentation:
- `contracts/firestore-schema.md` — Firestore document shapes
- `contracts/bigquery-schema.md` — BigQuery table definitions
- `contracts/api-web.md` — Web-facing API routes
- `contracts/api-admin.md` — Admin-facing API routes
- `contracts/gcs-conventions.md` — GCS path patterns
- `contracts/eval-standards.md` — Evaluation criteria and thresholds

## Commands

```bash
# Unified API
cd apps/api && pip install -e . && uvicorn backend.main:app --reload --port 8080

# Web UI
cd apps/web && npm install && npm run dev

# Admin UI
cd apps/admin && npm install && npm run dev

# Install all shared packages
pip install -e packages/common-python -e packages/db -e packages/integrations -e packages/capabilities

# Run tests
python -m pytest tests/

# Deploy unified API
bash apps/api/infra/deploy.sh
```

## Working in This Repo

- When modifying shared packages, run tests across all consumers.
- When changing an API endpoint, update the corresponding `contracts/` doc.
- Each app has its own `CLAUDE.md` with app-specific details. Read it before working in that app.
- Capabilities are in `packages/capabilities/` — each has a `runner.py` (stateless: identity in, report out).
- DB access is in `packages/db/` — never access Firestore/BQ directly from routers or agents.
