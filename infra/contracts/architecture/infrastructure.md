> Auto-generated from codebase on 2026-03-22.

# Infrastructure & Deployment

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

| Service | Stack | Cloud Run Name | Memory | CPU | Port | Public |
|---------|-------|----------------|--------|-----|------|--------|
| API (interactive) | FastAPI | `hephae-forge-api` | 512Mi | 1 | 8080 | No |
| Web Frontend | Next.js 16 | `hephae-forge-web` | 512Mi | 1 | 3000 | Yes |
| Admin Frontend | Next.js 14.1 | `hephae-admin-web` | 512Mi | 1 | 3000 | Yes |
| Crawl4AI | crawl4ai | `hephae-crawl4ai` | 2Gi | 2 | 11235 | No |

### Cloud Run Jobs

| Job | Stack | Cloud Run Name | Memory | CPU | Timeout | Purpose |
|-----|-------|----------------|--------|-----|---------|---------|
| Batch Runner | Python CLI | `hephae-forge-batch` | 4Gi | 2 | 3600s | Workflows, area research, Playwright-heavy work |

The API service is lightweight (no Playwright/Chromium). It delegates heavy work to the batch job
via `launch_batch_job()` using the Cloud Run Jobs v2 API. Browser operations (crawl, screenshot) on
the API service are proxied to the crawl4ai service via HTTP.

> Source: `infra/scripts/deploy.sh`, `infra/docker/Dockerfile.api`, `infra/docker/Dockerfile.batch`

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

### Government Data APIs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `BLS_API_KEY` | `str` | `""` | Bureau of Labor Statistics API key |
| `USDA_NASS_API_KEY` | `str` | `""` | USDA National Agricultural Statistics Service API key |

### Optional Data Source APIs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `USDA_FDC_API_KEY` | `str` | `""` | USDA FoodData Central API key |
| `YELP_API_KEY` | `str` | `""` | Yelp Fusion API key |
| `EIA_API_KEY` | `str` | `""` | Energy Information Administration API key |
| `FBI_API_KEY` | `str` | `""` | FBI Crime Data Explorer API key |
| `SCHOOLDIGGER_APP_ID` | `str` | `""` | SchoolDigger API application ID |
| `SCHOOLDIGGER_APP_KEY` | `str` | `""` | SchoolDigger API application key |

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
| `MONITOR_NOTIFY_EMAILS` | `str` | `""` | Comma-separated emails for workflow monitor and cron summary alerts |

### Dual-Model Synthesis

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `ANTHROPIC_API_KEY` | `str` | `""` | Anthropic API key for dual-model synthesis |

### Additional (set at deploy time, not in Settings class)

These are injected by deploy scripts or required as build-time env vars:

| Name | Used By | Description |
|------|---------|-------------|
| `GCP_PROJECT_ID` | All deploy scripts | GCP project ID (must be set before deploy) |
| `FIREBASE_API_KEY` | Web + Admin deploy | Firebase client API key (build arg for Next.js) |
| `BACKEND_URL` | Web + Admin runtime | Unified API Cloud Run URL (set automatically) |
| `NODE_ENV` | Web runtime | Set to `production` at deploy |
| `PYTHONUNBUFFERED` | API runtime | Set to `1` at deploy |
| `GCS_BUCKET` | StorageConfig | Legacy GCS bucket name |
| `GCS_BASE_URL` | StorageConfig | Legacy GCS base URL |
| `GCS_CDN_BUCKET` | StorageConfig | CDN GCS bucket name |
| `CDN_BASE_URL` | StorageConfig | CDN public base URL (e.g. `https://cdn.hephae.co`) |

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

## 4. Cloud Scheduler Jobs

| Job Name | Schedule | Target | Auth | Description |
|----------|----------|--------|------|-------------|
| `workflow-monitor` | Every 30 min | `GET /api/cron/workflow-monitor` | CRON_SECRET | Detect terminal workflows, send digest email |
| `workflow-dispatcher` | Every 5 min | `GET /api/cron/workflow-dispatcher` | CRON_SECRET | Start next queued workflow (one at a time) |
| `heartbeat-cycle` | Weekly | `GET /api/cron/heartbeat-cycle` | CRON_SECRET | Re-run capabilities for due heartbeats |
| `industry-pulse-cron` | **Sunday 3:00 AM ET (08:00 UTC)** | `GET /api/cron/industry-pulse` | CRON_SECRET | Generate national industry pulses for all active registered industries (NEW) |
| `weekly-pulse-cron` | Monday 6:00 AM ET (11:00 UTC) | `GET /api/cron/weekly-pulse` | CRON_SECRET | Generate zip-level pulses for all active registered zipcodes |

### Pulse Cron Sequence (Two-Layer Architecture)

The industry pulse cron runs **before** the weekly pulse cron to pre-compute national signals:

```
Sunday 3:00 AM ET    industry-pulse-cron
  |                    For each active registered industry:
  |                      - Fetch BLS CPI, USDA prices, FDA recalls
  |                      - Compute impact multipliers
  |                      - Match playbooks
  |                      - Generate LLM trend summary
  |                      - Save to industry_pulses collection
  |
  +-- 28 hours gap --+
                     |
Monday 6:00 AM ET    weekly-pulse-cron
                       For each active zip x businessType:
                         - Load industry pulse (cache hit)
                         - Fetch local signals only
                         - Merge + synthesize
                         - Save to weekly_pulses collection
```

This avoids N redundant BLS/USDA/FDA API calls (one per zip code) by fetching national data once per industry per week.

---

## 5. Deployment

### API Service + Batch Job

```bash
bash infra/scripts/deploy.sh              # Full deploy with prerequisite checks
bash infra/scripts/deploy.sh --skip-checks  # Skip secret/auth verification
```

Deploys two components from one script:

**API Service** (`hephae-forge-api` -- lightweight, no Playwright):
1. Builds Docker image via Cloud Build (`infra/docker/Dockerfile.api`, 900s timeout)
2. Resolves crawl4ai service URL
3. Deploys to Cloud Run as `hephae-forge-api` (512Mi, 1 vCPU)
4. Grants service account `roles/run.invoker` on the API service
5. Creates/updates Cloud Scheduler jobs:
   - `workflow-monitor` -- `GET /api/cron/workflow-monitor` every 30 min
   - `workflow-dispatcher` -- `GET /api/cron/workflow-dispatcher` every 5 min
   - `industry-pulse-cron` -- `GET /api/cron/industry-pulse` Sunday 3 AM ET (NEW)
   - `weekly-pulse-cron` -- `GET /api/cron/weekly-pulse` Monday 6 AM ET

**Batch Job** (`hephae-forge-batch` -- heavy, with Playwright):
1. Builds Docker image via Cloud Build (`infra/docker/Dockerfile.batch`, 1200s timeout)
2. Creates/updates Cloud Run Job (4Gi, 2 vCPU, 3600s timeout)
3. The API service launches job executions via `launch_batch_job()` (requires `roles/run.developer` on the service account)

Secrets injected at runtime (both): `GEMINI_API_KEY`, `BLS_API_KEY`, `FRED_API_KEY`, `GOOGLE_MAPS_API_KEY`, `FORGE_API_SECRET`, `FORGE_V1_API_KEY`, `CRON_SECRET`, `RESEND_API_KEY`, `ADMIN_EMAIL_ALLOWLIST`, `MONITOR_NOTIFY_EMAILS`

> Source: `infra/scripts/deploy.sh`, `infra/docker/Dockerfile.api`, `infra/docker/Dockerfile.batch`

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

## 6. Cloud Run Configuration

### Services

| Setting | API (`hephae-forge-api`) | Web (`hephae-forge-web`) | Admin (`hephae-admin-web`) | crawl4ai (`hephae-crawl4ai`) |
|---------|--------------------------|--------------------------|----------------------------|------------------------------|
| Memory | 512Mi | 512Mi | 512Mi | 2Gi |
| CPU | 1 | 1 | 1 | 2 |
| Timeout | 300s | 300s | 60s | 300s |
| Concurrency | 80 | _(default)_ | 100 | 160 |
| Min Instances | 1 | 0 | 0 | 0 |
| Max Instances | 5 | 5 | 3 | 3 |
| Auth | IAM-only | Public | Public | IAM-only |
| Playwright | No | N/A | N/A | Yes (built-in) |

### Jobs

| Setting | Batch (`hephae-forge-batch`) |
|---------|------------------------------|
| Memory | 4Gi |
| CPU | 2 |
| Task Timeout | 3600s (1 hour) |
| Max Retries | 1 |
| Playwright | Yes |
| Scale | 0 (scale-to-zero, launched on demand) |

> Source: `infra/scripts/deploy.sh`, `apps/web/infra/deploy.sh`, `apps/admin/infra/deploy.sh`

### Required IAM Roles for Service Account

| Role | Purpose |
|------|---------|
| `roles/datastore.user` | Firestore read/write |
| `roles/bigquery.dataEditor` | BigQuery insert |
| `roles/bigquery.jobUser` | BigQuery run queries |
| `roles/storage.objectAdmin` | GCS upload/delete |
| `roles/secretmanager.secretAccessor` | Read secrets at runtime |
| `roles/run.invoker` | Invoke Cloud Run services (service-to-service auth) |
| `roles/run.developer` | Launch Cloud Run Job executions (`run.jobs.run`, `run.jobs.runWithOverrides`) |

> **Note:** `roles/run.developer` is critical -- without it, the API service cannot launch batch jobs and workflows will get stuck in `discovery` phase after the dispatcher sets the phase but fails to start the job.

---

## 7. Bootstrap

Run `bash infra/setup.sh` to initialize a fresh GCP project. The script is idempotent (safe to re-run). Use `--check-only` to audit without creating anything.

### What it provisions

| Step | Resource | Details |
|------|----------|---------|
| 1 | GCP APIs | Enables 8 APIs: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Firestore, BigQuery, GCS, Cloud Scheduler, Cloud Tasks |
| 2 | Service Account | `hephae-forge@$PROJECT_ID.iam.gserviceaccount.com` with 7 IAM roles (see above) |
| 3 | Artifact Registry | Docker repo `cloud-run-source-deploy` in `us-central1` |
| 4 | Secret Manager | Creates 1 required secret (`GEMINI_API_KEY`) and 9 optional secrets |
| 5 | GCS Buckets | Legacy bucket (`everything-hephae`) and CDN bucket (`$PROJECT_ID-prod-cdn-assets`), both with public read access |
| 6 | Firestore | Default database in Native mode, `us-central1` |
| 7 | Cloud Tasks | Queue `hephae-agent-queue` (10 dispatches/sec, 5 concurrent, 3 max attempts) |
| 8 | BigQuery | Dataset `hephae` (location `US`), checks for tables `analyses`, `discoveries`, `interactions` |

> Source: `infra/setup.sh`

---

## 8. Firestore Collections (Pulse-Related)

The two-layer pulse architecture adds these Firestore collections:

| Collection | Document Key | Purpose |
|------------|-------------|---------|
| `registered_industries` | `{industryKey}` | Registry of industries for national pulse cron |
| `industry_pulses` | `{industryKey}-{weekOf}` | Pre-computed national signals, impact multipliers, playbooks, trend summaries |
| `registered_zipcodes` | `{zipCode}` | Registry of zip codes for weekly zip-level pulse cron |
| `weekly_pulses` | auto-ID | Zip-level weekly pulse documents with merged national + local signals |
| `pulse_jobs` | auto-ID | Job tracking for individual pulse generation runs |
| `pulse_batch_work_items` | auto-ID | Work items for county-wide batch pulse runs |
| `zipcode_profiles` | `{zipCode}` | Discovered data source profiles for each zip code |

See `infra/contracts/firestore-schema.md` for full document shapes.
