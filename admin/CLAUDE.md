# CLAUDE.md — Admin App (internal dashboard)

> Part of the hephae-forge monorepo. See `../CLAUDE.md` for cross-app standards.
> See `../contracts/` for shared schemas, API contracts, and eval standards.

This is the internal admin/CI dashboard. It orchestrates and evaluates AI capabilities provided by the web app (`../web/`).

## Architecture: 2-Service Split

- **hephae-admin-api** (Python FastAPI, port 8000) — Agents, workflow engine, orchestrators, Firestore persistence, SSE streaming
- **hephae-admin-web** (Next.js 14.1, port 3000) — Pure UI proxy. All `/api/*` requests rewrite to the Python backend.

## Commands

```bash
# Backend
pip install -e .                    # Install Python deps
uvicorn backend.main:app --reload   # Start backend (localhost:8000)

# Frontend
npm install && npm run dev          # Start frontend (localhost:3000, proxies /api/* to :8000)
npm run build                       # Production build
npm run lint                        # ESLint
npm run test                        # Vitest unit tests
npm run test:e2e                    # Playwright E2E tests

# Docker
cd infra && docker-compose up       # Run both services locally

# Deploy
bash infra/deploy.sh                # Cloud Run deployment
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Google ADK, Pydantic v2
- **Frontend:** Next.js 14.1 (App Router), TypeScript, Tailwind CSS
- **AI Models:** Gemini via Google ADK (see `../CLAUDE.md` for model tiers)
- **Database:** Firebase/Firestore, BigQuery
- **Email:** Resend API
- **Infrastructure:** Docker (2 containers), Cloud Run (2 services)
- **Path alias:** `@/*` maps to `./src/*`

## Multi-Agent Pipeline (5 workflow phases)

1. **Discovery** — Scans zip codes for businesses (calls web app's `/api/v1/discover`)
2. **Enrichment** — Gets full profiles from web app
3. **Analysis** — Runs 4 capabilities via web app API (SEO, traffic, competitive, margin)
4. **Evaluation** — 4 QA evaluator agents validate outputs (see `../contracts/eval-standards.md`)
5. **Approval** — Pauses for human review
6. **Outreach** — Formats content, sends via Resend email API

## How Admin Calls Web App

See `../contracts/api-web.md` for the full contract. Key endpoints:

| Capability | Endpoint | Response |
|---|---|---|
| Discovery | `POST /api/v1/discover` | `EnrichedProfile` |
| SEO | `POST /api/capabilities/seo` | `SeoReport` |
| Traffic | `POST /api/capabilities/traffic` | `ForecastResponse` |
| Competitive | `POST /api/capabilities/competitive` | `CompetitiveReport` |
| Margin | `POST /api/v1/analyze` | `SurgicalReport` |

Auth: HMAC headers via `backend/lib/forge_auth.py`.

## Backend Structure

```
backend/
├── main.py                     # FastAPI app, CORS, health endpoint
├── config.py                   # AgentModels, ThinkingPresets, Settings
├── types.py                    # All Pydantic v2 models
├── agents/                     # Google ADK agents
│   ├── discovery/              # zipcode_scanner, county_resolver
│   ├── research/               # 7 research agents
│   ├── evaluators/             # seo, traffic, competitive, margin_surgeon
│   ├── insights/               # insights_agent
│   └── outreach/               # communicator
├── orchestrators/              # zipcode, area, sector research
├── workflow/
│   ├── engine.py               # State machine + SSE
│   ├── phases/                 # discovery, enrichment, analysis, evaluation, outreach
│   └── capabilities/           # registry + display
├── routers/                    # 11 FastAPI routers
├── lib/                        # Firebase, BQ, email, auth, DB modules
└── services/                   # test_runner.py
```

## Model Tiering

See `../CLAUDE.md` for cross-app model strategy. This app's specific usage:
- **PRIMARY** (gemini-3.1-flash-lite-preview): Discovery, research, formatting, outreach
- **ENHANCED** (gemini-3.0-flash-preview): Evaluators, industry analysis
- **Thinking:** MEDIUM for evaluators, HIGH for complex analysis
- **Fallback:** PRIMARY -> gemini-2.5-flash-lite, ENHANCED -> gemini-2.5-flash (on 429/503/529)

## Environment Variables

- `FORGE_URL` — Web app API base URL (also reads legacy `MARGIN_SURGEON_URL`)
- `GEMINI_API_KEY` — Google AI API key
- `RESEND_API_KEY` / `RESEND_FROM_EMAIL` — Email sending
- `CRON_SECRET` — Bearer token for cron endpoints
- `BACKEND_URL` — Python backend URL (for Next.js in production)
- `GOOGLE_APPLICATION_CREDENTIALS` — Firebase/GCP service account (local dev)

## Data Persistence

- **Firestore:** See `../contracts/firestore-schema.md`
- **BigQuery:** See `../contracts/bigquery-schema.md`
- **GCS:** See `../contracts/gcs-conventions.md`
