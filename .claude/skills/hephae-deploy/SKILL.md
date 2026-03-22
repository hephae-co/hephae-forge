---
name: hephae-deploy
description: Deploy Hephae services to Cloud Run — API (forge), web frontend, admin frontend, or all. Pre-flight checks, build, deploy, post-deploy verification.
argument-hint: [all | api | web | admin]
---

# Deploy — Cloud Run Deployment Orchestrator

Deploys Hephae services to Google Cloud Run with pre-flight checks, build monitoring, and post-deploy verification.

## Input

| Arg | What It Deploys | Script |
|-----|----------------|--------|
| `all` | API + Web + Admin (sequential) | All 3 scripts |
| `api` or `forge` | Unified API + batch job | `infra/scripts/deploy.sh` |
| `web` | Customer-facing web frontend | `apps/web/infra/deploy.sh` |
| `admin` | Admin dashboard frontend | `apps/admin/infra/deploy.sh` |

Arguments: $ARGUMENTS

If no args, ask: "What do you want to deploy? (all / api / web / admin)"

---

## PHASE 1: PRE-FLIGHT CHECKS

Run ALL of these before deploying. Stop if any fail.

### 1a. Git Status

```bash
echo "=== Git Status ==="
git status --short
echo "Branch: $(git branch --show-current)"
echo "Latest commit: $(git log --oneline -1)"
echo "Unpushed: $(git log origin/main..HEAD --oneline | wc -l | tr -d ' ') commits"
```

**STOP if:**
- There are uncommitted changes → ask user to commit first
- There are unpushed commits → ask user to push first
- Not on `main` branch → warn (deploy from feature branch is risky)

### 1b. GCP Auth

```bash
echo "=== GCP Auth ==="
gcloud auth print-access-token > /dev/null 2>&1 && echo "OK" || echo "FAIL — run: gcloud auth login"
PROJECT=$(gcloud config get-value project 2>/dev/null)
echo "Project: $PROJECT"
```

**STOP if:** Auth fails or project is not set.

### 1c. Check Required Secrets

```bash
PROJECT=$(gcloud config get-value project 2>/dev/null)
echo "=== Secrets ==="
for secret in GEMINI_API_KEY FORGE_API_SECRET CRON_SECRET RESEND_API_KEY; do
  if gcloud secrets versions access latest --secret=$secret --project=$PROJECT > /dev/null 2>&1; then
    echo "  $secret: OK"
  else
    echo "  $secret: MISSING"
  fi
done
```

**WARN if:** Any secret is missing (deploy may still work but features will be degraded).

### 1d. Check What Changed

```bash
echo "=== Changes since last deploy ==="
# Find the last deploy tag or use recent commits
git log --oneline -10
echo ""
echo "Files changed (last 5 commits):"
git diff --stat HEAD~5..HEAD | tail -20
```

Show the user what's about to be deployed. Ask for confirmation: "Deploy these changes? (y/n)"

---

## PHASE 2: DEPLOY

### For API (`api` or `forge`):

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
bash infra/scripts/deploy.sh --skip-checks
```

This script:
1. Builds Docker image from `infra/docker/Dockerfile.api`
2. Pushes to Artifact Registry
3. Deploys Cloud Run service `hephae-forge-api` (2Gi, 2 CPU, 80 concurrency)
4. Deploys Cloud Run job `hephae-forge-batch`
5. Creates/updates Cloud Scheduler jobs (workflow-monitor, workflow-dispatcher, industry-pulse-cron)
6. Sets all secrets as env vars

**Timeout:** ~5-10 minutes for build + deploy.

### For Web (`web`):

**IMPORTANT:** Frontend deploy scripts require env vars that the API script auto-sources from `.env`. Always source `.env` first or pass them explicitly:

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
# Source .env for GCP_PROJECT_ID, FIREBASE_API_KEY, etc.
set -a; source .env 2>/dev/null; set +a
bash apps/web/infra/deploy.sh --skip-checks
```

If `.env` doesn't exist, set manually:
```bash
GCP_PROJECT_ID=hephae-co-dev \
FIREBASE_API_KEY=$(gcloud secrets versions access latest --secret=FIREBASE_API_KEY) \
bash apps/web/infra/deploy.sh --skip-checks
```

This script:
1. Builds Next.js image
2. Deploys Cloud Run service `hephae-forge-web` (512Mi, 1 CPU)
3. Sets `BACKEND_URL` to API service URL
4. Public access (--allow-unauthenticated)

### For Admin (`admin`):

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
set -a; source .env 2>/dev/null; set +a
bash apps/admin/infra/deploy.sh --skip-checks
```

Same env var requirements as web.

### For All:

Deploy in order: **API first** (backend must be up before frontends), then web and admin in parallel:

```bash
# 1. API first
bash infra/scripts/deploy.sh --skip-checks

# 2. Web + Admin in parallel
bash apps/web/infra/deploy.sh --skip-checks &
bash apps/admin/infra/deploy.sh --skip-checks &
wait
```

**Run each deploy script via Bash with `run_in_background` if deploying all — they're independent after API is done.**

---

## PHASE 3: POST-DEPLOY VERIFICATION

After deploy completes, verify each service is healthy.

### 3a. API Health Check

```bash
API_URL=$(gcloud run services describe hephae-forge-api --region=us-central1 --format="value(status.url)" 2>/dev/null)
echo "API URL: $API_URL"
curl -s "$API_URL/api/health" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Status: {d.get(\"status\", \"?\")}, Service: {d.get(\"service\", \"?\")}')
"
```

### 3b. Web Health Check

```bash
WEB_URL=$(gcloud run services describe hephae-forge-web --region=us-central1 --format="value(status.url)" 2>/dev/null)
echo "Web URL: $WEB_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_URL")
echo "HTTP: $HTTP_CODE"
```

### 3c. Admin Health Check

```bash
ADMIN_URL=$(gcloud run services describe hephae-admin-web --region=us-central1 --format="value(status.url)" 2>/dev/null)
echo "Admin URL: $ADMIN_URL"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ADMIN_URL")
echo "HTTP: $HTTP_CODE"
```

### 3d. Check Cloud Run Revision

```bash
echo "=== Active Revisions ==="
for svc in hephae-forge-api hephae-forge-web hephae-admin-web; do
  rev=$(gcloud run services describe $svc --region=us-central1 --format="value(status.latestReadyRevisionName)" 2>/dev/null)
  echo "  $svc: $rev"
done
```

### 3e. Check for Startup Errors

```bash
PROJECT=$(gcloud config get-value project 2>/dev/null)
echo "=== Recent Errors (last 5 min) ==="
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --limit=5 --freshness=5m \
  --format="table(timestamp, resource.labels.service_name, textPayload)" \
  --project=$PROJECT
```

---

## PHASE 4: REPORT

```markdown
## Deploy Complete

| Service | Status | URL | Revision |
|---------|--------|-----|----------|
| API     | {OK/FAIL} | {url} | {rev} |
| Web     | {OK/FAIL} | {url} | {rev} |
| Admin   | {OK/FAIL} | {url} | {rev} |

**Commit:** {hash} — {message}
**Deploy time:** {duration}
**Errors:** {any errors from step 3e}
```

---

## ROLLBACK

If something goes wrong, rollback to the previous revision:

```bash
# Find previous revision
gcloud run revisions list --service=hephae-forge-api --region=us-central1 --limit=3

# Route traffic back to previous revision
gcloud run services update-traffic hephae-forge-api \
  --region=us-central1 \
  --to-revisions=PREVIOUS_REVISION=100
```

**Do NOT run rollback automatically.** Show the commands and let the user decide.

---

## Key Files

| Area | File |
|------|------|
| API deploy | `infra/scripts/deploy.sh` |
| Web deploy | `apps/web/infra/deploy.sh` |
| Admin deploy | `apps/admin/infra/deploy.sh` |
| API Dockerfile | `infra/docker/Dockerfile.api` |
| Batch Dockerfile | `infra/docker/Dockerfile.batch` |
| Cloud Scheduler setup | Inside `infra/scripts/deploy.sh` (bottom) |

## What NOT To Do

- Do NOT deploy with uncommitted changes — commit and push first.
- Do NOT deploy web/admin before API — the backend must be up for the frontends to work.
- Do NOT skip post-deploy verification — always check health endpoints.
- Do NOT rollback automatically — show the command and let the user decide.
- Do NOT deploy during an active workflow or pulse cron — check first.
