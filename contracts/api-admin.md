# Admin App API (published by `admin/`)

> Admin's own endpoints, served by its FastAPI backend at `/api/*`.

## Base URL

```
# Local: http://localhost:8000 (proxied via Next.js at :3000)
# Production: https://hephae-admin-1096334123076.us-central1.run.app
```

## Endpoints

### Workflows
- `POST /api/workflows` — Create workflow (zip codes)
- `POST /api/workflows/county` — Create workflow (county-based)
- `GET /api/workflows` — List all workflows
- `GET /api/workflows/{id}` — Get workflow details
- `GET /api/workflows/{id}/stream` — SSE stream for workflow progress
- `PATCH /api/workflows/{id}` — Update workflow
- `DELETE /api/workflows/{id}` — Delete workflow
- `POST /api/workflows/{id}/approve` — Approve businesses for outreach
- `POST /api/workflows/{id}/resume` — Resume failed workflow

### Research
- `GET /api/research/businesses` — List researched businesses
- `DELETE /api/research/businesses` — Delete businesses
- `POST /api/research/actions` — Research actions (re-analyze, etc.)
- `/api/zipcode-research/*` — Zip code research CRUD + run
- `/api/area-research/*` — Area research with SSE streaming
- `/api/sector-research/*` — Sector research CRUD + run
- `/api/combined-context/*` — Combined context CRUD

### Testing
- `POST /api/run-tests` — Execute test suite against web app
- `GET /api/run-tests` — Fetch test run history
- `GET /api/cron/run-analysis` — Cron-triggered analysis (secured with CRON_SECRET)

### Other
- `GET /api/health` — Health check
- `/api/fixtures/*` — Test fixtures CRUD
