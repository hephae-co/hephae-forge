# CLAUDE.md — Unified API (backend service)

> Part of the hephae-forge monorepo. See `../../CLAUDE.md` for cross-app standards.

This is the unified backend API serving both the web and admin UIs. It replaces the separate web-api and admin-api services.

## Commands

```bash
pip install -e . && uvicorn hephae_api.main:app --reload --port 8080
# Or with all packages:
pip install -e ../../lib/common -e ../../lib/db -e ../../lib/integrations -e ../../agents -e .
```

## API Structure

```
hephae_api/
├── main.py                     # FastAPI app, CORS, health endpoint
├── config.py                   # Merged Settings + AgentVersions
├── types.py                    # Merged Pydantic v2 models
├── lib/
│   └── auth.py                 # Request auth (re-exports from hephae_common)
├── routers/
│   ├── web/                    # Routes serving web frontend (10 routers)
│   ├── admin/                  # Routes serving admin frontend (13 routers)
│   ├── v1/                     # Legacy backward-compat routes (5 routers)
│   └── batch/                  # Cloud Tasks / Cron routes
└── workflows/                  # Workflow engine (from admin)
    ├── engine.py               # State machine + SSE streaming
    ├── phases/                 # discovery, enrichment, analysis, evaluation, outreach
    ├── capabilities/           # registry (maps to runner functions), display
    ├── orchestrators/          # zipcode, area, sector research
    ├── agents/                 # Workflow-specific agents (evaluators, research, etc.)
    └── test_runner.py          # Direct runner calls for testing
```

## Key Architectural Decisions

1. **No inter-service HTTP** — Capabilities are direct Python imports via `hephae-agents` package
2. **Environment-based CORS** — `ALLOWED_ORIGINS` env var (default `*`)
3. **Capability registry** uses `runner` functions (not HTTP endpoints)
4. **SSE streaming** via Starlette native `StreamingResponse` for workflow progress

## Environment Variables (~30)

See `hephae_api/config.py` for the full list. Key ones:
- `GEMINI_API_KEY` — Google AI API key
- `PORT` — Server port (default 8080, Cloud Run sets this)
- `ALLOWED_ORIGINS` — CORS origins (comma-separated, default `*`)
- `FORGE_API_SECRET` — HMAC auth for UI→API calls
- `FORGE_V1_API_KEY` — API key for v1 endpoints
- `CRON_SECRET` — Bearer token for cron endpoints
