# Infrastructure & Deployment
> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

---

## 1. GCP Topology

All services deploy to a single GCP project and region.

| Property | Value |
|----------|-------|
| Region | `us-central1` |
| Project | `$GCP_PROJECT_ID` (env var) |
| Service Account | `hephae-forge@$PROJECT_ID.iam.gserviceaccount.com` |
| Artifact Registry | `cloud-run-source-deploy` (Docker, `us-central1`) |

### Cloud Run Services

| Service | Stack | Cloud Run Name | Port | Public |
|---------|-------|----------------|------|--------|
| Unified API | FastAPI | `hephae-forge-api` | 8080 | No (`--no-allow-unauthenticated`) |
| Web Frontend | Next.js 16 | `hephae-forge-web` | 3000 | Yes (`--allow-unauthenticated`) |
| Admin Frontend | Next.js 14.1 | `hephae-admin-web` | 3000 | Yes (`--allow-unauthenticated`) |
| Crawl4AI | crawl4ai | `hephae-crawl4ai` | -- | Referenced by API deploy; deployed separately |

> Source: `infra/scripts/deploy.sh`, `apps/web/infra/deploy.sh`, `apps/admin/infra/deploy.sh`

---

## 2. Environment Variables

All variables are defined in the `Settings` class via `pydantic_settings.BaseSettings`.

> Source: `apps/api/hephae_api/config.py`

### Core

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `GEMINI_API_KEY` | `str` | `""` | Google Gemini AI API key |
| `PORT` | `int` | `8080` | Server listen port (Cloud Run sets this automatically) |
| `ALLOWED_ORIGINS` | `str` | `"*"` | CORS allowed origins (comma-separated) |
| `API_BASE_URL` | `str` | `""` | This service's own URL, used for Cloud Tasks callbacks |
| `CRAWL4AI_URL` | `str` | `""` | URL of the crawl4ai Cloud Run service |

### Auth

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `FORGE_API_SECRET` | `str` | `""` | HMAC-SHA256 secret for UI-to-API request signing |
| `FORGE_V1_API_KEY` | `str` | `""` | API key for legacy v1 endpoints |
| `CRON_SECRET` | `str` | `""` | Bearer token for cron/scheduler endpoints |
| `ADMIN_EMAIL_ALLOWLIST` | `str` | `""` | Comma-separated list of allowed admin emails |

### Firebase / GCP

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `FIREBASE_PROJECT_ID` | `str` | `""` | Firebase project ID for Firestore access |
| `BIGQUERY_PROJECT_ID` | `str` | `""` | GCP project ID for BigQuery queries |
| `GOOGLE_CLOUD_PROJECT` | `str` | `""` | General GCP project ID (ADC) |

### Email

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `RESEND_API_KEY` | `str` | `""` | Resend email service API key |
| `RESEND_FROM_EMAIL` | `str` | `"onboarding@resend.dev"` | Sender address for outbound emails |

### External APIs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `BLS_API_KEY` | `str` | `""` | Bureau of Labor Statistics API key |
| `USDA_NASS_API_KEY` | `str` | `""` | USDA National Agricultural Statistics Service API key |

### Social Media

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `X_API_KEY` | `str` | `""` | X (Twitter) API consumer key |
| `X_API_SECRET` | `str` | `""` | X (Twitter) API consumer secret |
| `X_ACCESS_TOKEN` | `str` | `""` | X (Twitter) access token |
| `X_ACCESS_SECRET` | `str` | `""` | X (Twitter) access token secret |
| `FACEBOOK_PAGE_TOKEN` | `str` | `""` | Facebook Page access token |
| `FACEBOOK_PAGE_ID` | `str` | `""` | Facebook Page ID for posting |
| `INSTAGRAM_ACCESS_TOKEN` | `str` | `""` | Instagram Graph API access token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | `str` | `""` | Instagram Business Account ID |

### Batch / Evaluation

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `VERTEX_AI_LOCATION` | `str` | `"us-central1"` | Vertex AI region for batch evaluation jobs |
| `BATCH_EVAL_ENABLED` | `bool` | `true` | Enable/disable batch evaluation pipeline |
| `BATCH_EVAL_GCS_BUCKET` | `str` | `"hephae-batch-evaluations"` | GCS bucket for batch evaluation input/output |
| `BATCH_EVAL_FALLBACK_TIMEOUT` | `int` | `300` | Seconds before falling back from batch to inline evaluation |

### Monitoring

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `MONITOR_NOTIFY_EMAILS` | `str` | `""` | Comma-separated emails for workflow monitor alerts |

### Additional (set at deploy time, not in Settings class)

These are injected by deploy scripts or required as build-time env vars:

| Name | Used By | Description |
|------|---------|-------------|
| `GCP_PROJECT_ID` | All deploy scripts | GCP project ID (must be set before deploy) |
| `FIREBASE_API_KEY` | Web + Admin deploy | Firebase client API key (build arg for Next.js) |
| `BACKEND_URL` | Web + Admin runtime | Unified API Cloud Run URL (set automatically) |
| `NODE_ENV` | Web runtime | Set to `production` at deploy |
| `PYTHONUNBUFFERED` | API runtime | Set to `1` at deploy |
| `RESEND_FROM_EMAIL` | API deploy | Sender email (defaults to `onboarding@resend.dev`) |

---

## 3. Storage

### Firestore

| Property | Value |
|----------|-------|
| Mode | Native |
| Database | Default (auto-initialized via ADC) |
| Region | `us-central1` |
| Security Rules | All client access denied (`allow read, write: if false`) |

> Source: `infra/setup.sh` (step 6)

### BigQuery

| Property | Value |
|----------|-------|
| Dataset | `hephae` (within `$GCP_PROJECT_ID`) |
| Location | `US` |

| Table | Notes |
|-------|-------|
| `analyses` | Auto-created on first write |
| `discoveries` | Auto-created on first write |
| `interactions` | Auto-created on first write |

> Source: `infra/setup.sh` (step 8)

### GCS Buckets

| Bucket | Env Var | Default | Access | Purpose |
|--------|---------|---------|--------|---------|
| Legacy | `GCS_BUCKET` | `everything-hephae` | Public read (`allUsers`) | Menu screenshots, menu HTML |
| CDN | `GCS_CDN_BUCKET` | `$PROJECT_ID-prod-cdn-assets` | Public read (`allUsers`) | Reports, social cards (served via `CDN_BASE_URL`) |
| Batch Eval | `BATCH_EVAL_GCS_BUCKET` | `hephae-batch-evaluations` | Private | Batch evaluation input/output files |

> Source: `infra/setup.sh` (step 5), `apps/api/hephae_api/config.py`

---

## 4. Deployment

### Unified API

```bash
bash infra/scripts/deploy.sh              # Full deploy with prerequisite checks
bash infra/scripts/deploy.sh --skip-checks  # Skip secret/auth verification
```

Steps:
1. Builds Docker image via Cloud Build (`infra/docker/Dockerfile.fastapi`, 900s timeout)
2. Resolves crawl4ai service URL
3. Deploys to Cloud Run as `hephae-forge-api`
4. Grants service account `roles/run.invoker` on the API service
5. Creates/updates Cloud Scheduler jobs:
   - `workflow-monitor` — `GET /api/cron/workflow-monitor` every 30 min
   - `workflow-dispatcher` — `GET /api/cron/workflow-dispatcher` every 5 min

Secrets injected at runtime: `GEMINI_API_KEY`, `BLS_API_KEY`, `FRED_API_KEY`, `GOOGLE_MAPS_API_KEY`, `FORGE_API_SECRET`, `FORGE_V1_API_KEY`, `CRON_SECRET`, `RESEND_API_KEY`, `ADMIN_EMAIL_ALLOWLIST`, `MONITOR_NOTIFY_EMAILS`

> Source: `infra/scripts/deploy.sh`

### Web Frontend

```bash
bash apps/web/infra/deploy.sh
bash apps/web/infra/deploy.sh --skip-checks
```

Steps:
1. Builds Docker image via Cloud Build (`apps/web/infra/Dockerfile.nextjs`, 600s timeout)
2. Resolves API service URL
3. Deploys to Cloud Run as `hephae-forge-web` with `BACKEND_URL` pointing to the API

Secrets injected at runtime: `FORGE_API_SECRET`

> Source: `apps/web/infra/deploy.sh`

### Admin Frontend

```bash
bash apps/admin/infra/deploy.sh
bash apps/admin/infra/deploy.sh --skip-checks
```

Steps:
1. Builds Docker image via Cloud Build (`apps/admin/infra/Dockerfile.nextjs`, 600s timeout)
2. Resolves API service URL
3. Deploys to Cloud Run as `hephae-admin-web` with `BACKEND_URL` pointing to the API

No secrets injected at runtime (admin uses `BACKEND_URL` only).

> Source: `apps/admin/infra/deploy.sh`

---

## 5. Cloud Run Configuration

| Setting | API (`hephae-forge-api`) | Web (`hephae-forge-web`) | Admin (`hephae-admin-web`) |
|---------|--------------------------|--------------------------|----------------------------|
| Memory | 2Gi | 512Mi | 512Mi |
| CPU | 2 | 1 | 1 |
| Timeout | 1800s (30 min) | 300s (5 min) | 60s |
| Concurrency | 80 | _(default)_ | 100 |
| Min Instances | 1 | 0 | 0 |
| Max Instances | 5 | 5 | 3 |
| Auth | IAM-only | Public | Public |

> Source: `infra/scripts/deploy.sh`, `apps/web/infra/deploy.sh`, `apps/admin/infra/deploy.sh`

---

## 6. Bootstrap

Run `bash infra/setup.sh` to initialize a fresh GCP project. The script is idempotent (safe to re-run). Use `--check-only` to audit without creating anything.

### What it provisions

| Step | Resource | Details |
|------|----------|---------|
| 1 | GCP APIs | Enables 8 APIs: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore, BigQuery, GCS, Cloud Scheduler, Cloud Tasks |
| 2 | Service Account | `hephae-forge@$PROJECT_ID.iam.gserviceaccount.com` with 6 IAM roles: `datastore.user`, `bigquery.dataEditor`, `bigquery.jobUser`, `storage.objectAdmin`, `secretmanager.secretAccessor`, `run.invoker` |
| 3 | Artifact Registry | Docker repo `cloud-run-source-deploy` in `us-central1` |
| 4 | Secret Manager | Creates 1 required secret (`GEMINI_API_KEY`) and 8 optional secrets (`BLS_API_KEY`, `FRED_API_KEY`, `GOOGLE_MAPS_API_KEY`, `FORGE_API_SECRET`, `FORGE_V1_API_KEY`, `CRON_SECRET`, `RESEND_API_KEY`, `ADMIN_EMAIL_ALLOWLIST`, `FIREBASE_API_KEY`). Optional secrets get a `placeholder` value. |
| 5 | GCS Buckets | Legacy bucket (`everything-hephae`) and CDN bucket (`$PROJECT_ID-prod-cdn-assets`), both with public read access |
| 6 | Firestore | Default database in Native mode, `us-central1` |
| 7 | Cloud Tasks | Queue `hephae-agent-queue` (10 dispatches/sec, 5 concurrent, 3 max attempts) |
| 8 | BigQuery | Dataset `hephae` (location `US`), checks for tables `analyses`, `discoveries`, `interactions` |

> Source: `infra/setup.sh`
