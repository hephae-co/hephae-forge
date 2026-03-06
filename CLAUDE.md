# CLAUDE.md — Hephae Forge Monorepo

This is the root of the hephae-forge monorepo. It contains two apps and shared packages.

## Repository Structure

```
hephae-forge/
├── web/                   # Customer-facing web app (hephae.co)
├── admin/                 # Internal admin/CI dashboard
├── packages/
│   ├── common-python/     # Shared Python code (Firebase, auth, models)
│   └── common-ts/         # Shared TypeScript code (types, Firebase client)
└── contracts/             # Shared API & data contracts (documentation)
```

## Apps

- **`web/`** — The customer-facing product at hephae.co. Analyzes restaurants using AI agents (margin surgery, SEO audit, traffic forecast, competitive analysis). Next.js frontend + FastAPI backend.
- **`admin/`** — Internal admin dashboard that orchestrates and evaluates web app capabilities. Runs multi-phase workflows: discovery, enrichment, analysis, evaluation, outreach. Next.js frontend + FastAPI backend.

Admin depends on web's API endpoints. Web is standalone.

## Cross-App Standards

### Model Strategy

All AI agents across both apps use Google Gemini via Google ADK.

| Tier | Model | Use Case |
|------|-------|----------|
| PRIMARY | `gemini-3.1-flash-lite-preview` | All standard agents (discovery, research, formatting, outreach) |
| PRIMARY_FALLBACK | `gemini-2.5-flash-lite` | Automatic fallback on 429/503/529 |
| ENHANCED | `gemini-3.0-flash-preview` | Complex analysis (SEO auditor) |
| CREATIVE_VISION | `gemini-3-pro-image-preview` | Image generation |

Thinking modes: MEDIUM for evaluators, HIGH for competitive/market positioning.

When upgrading model tiers, update BOTH `web/backend/config.py` and `admin/backend/config.py`, or (once extracted) `packages/common-python/hephae_common/model_config.py`.

### Database Rules (strictly enforced)

1. **No blobs in Firestore or BigQuery** — upload binary assets to GCS (`everything-hephae` bucket), store only the resulting URL.
2. **`zipCode` is first-class** — always a top-level field, never derived from address at query time.
3. **No growing arrays in Firestore** — no `reports[]`, no `analyses[]`. Historical data goes to BigQuery. Firestore stores only current state.
4. **Use `update()` with dotted paths** for nested Firestore fields. `set({merge:true})` only for new docs.

### Agent Versioning

Every agent has a semantic version in its app's `config.py` under `AgentVersions`.

- MAJOR: output schema change (fields added/removed/renamed)
- MINOR: logic change, same schema
- PATCH: prompt wording, no logic change

Bump the version in the same commit as the breaking change.

### Authentication

| Context | Mechanism |
|---------|-----------|
| Web app internal | Firebase Admin SDK (server-side only, no client DB access) |
| Admin → Web API calls | HMAC-SHA256 signing (`FORGE_API_SECRET`) for capability endpoints; API key header for v1 endpoints |
| Cloud Run services | GCP identity tokens via metadata server |
| Firestore rules | All client access denied (`allow read, write: if false`) |

### GCP Infrastructure

| Component | Value |
|-----------|-------|
| GCP Project | `hephae-co-dev` |
| Firestore | Default (auto-initialized via ADC) |
| BigQuery Dataset | `hephae-co-dev.hephae` |
| GCS Bucket | `everything-hephae` |
| GCS Public Base | `https://storage.googleapis.com/everything-hephae/` |

### Evaluation Standards (admin evaluators)

Admin evaluator agents validate web app capability outputs:
- **Pass threshold:** score >= 80 AND !isHallucinated
- **Evaluator model:** ENHANCED tier + MEDIUM thinking
- All 4 capabilities (SEO, traffic, competitive, margin) have dedicated evaluator agents

When changing a web app agent's output schema, check that admin's corresponding evaluator still works.

## Contracts

See `contracts/` for shared documentation:
- `contracts/firestore-schema.md` — Firestore document shapes
- `contracts/bigquery-schema.md` — BigQuery table definitions
- `contracts/api-web.md` — Web app's published API (for admin consumption)
- `contracts/api-admin.md` — Admin app's published API
- `contracts/gcs-conventions.md` — GCS path patterns
- `contracts/eval-standards.md` — Evaluation criteria and thresholds

## Shared Packages

### `packages/common-python/` (`hephae-common`)
Shared Python code installed as a local path dependency by both apps.
```bash
pip install -e packages/common-python
```

### `packages/common-ts/` (`@hephae/common`)
Shared TypeScript code resolved via npm workspaces.
```json
"@hephae/common": "workspace:*"
```

## Working in This Repo

- When modifying shared types/models, run tests in BOTH `web/` and `admin/`.
- When changing a web app API endpoint, update `contracts/api-web.md` in the same commit.
- When changing admin's expectations of web, update `contracts/api-admin.md`.
- Each app has its own `CLAUDE.md` with app-specific details. Read it before working in that app.
