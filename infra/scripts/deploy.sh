#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy unified API to Cloud Run
#
# Usage:
#   bash infra/scripts/deploy.sh
#   bash infra/scripts/deploy.sh --skip-checks
# ─────────────────────────────────────────────────────────────

# Auto-source .env from repo root if GCP_PROJECT_ID is not already set
SCRIPT_DIR_EARLY="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT_EARLY="$(cd "$SCRIPT_DIR_EARLY/../.." && pwd)"
if [ -z "${GCP_PROJECT_ID:-}" ] && [ -f "$REPO_ROOT_EARLY/.env" ]; then
  set -a; source "$REPO_ROOT_EARLY/.env"; set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var or add it to .env}"
REGION="us-central1"
BUILD_REGION="us-central1"
REPO="cloud-run-source-deploy"
TAG=$(git rev-parse --short HEAD)
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

API_SERVICE="hephae-forge-api"
API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${API_SERVICE}:${TAG}"

CRAWL4AI_SERVICE="hephae-crawl4ai"

# Resolve repo root (build context must be monorepo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ─────────────────────────────────────────────────────────────
# Parse flags
# ─────────────────────────────────────────────────────────────
SKIP_CHECKS=false
for arg in "$@"; do
  case $arg in
    --skip-checks) SKIP_CHECKS=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ─────────────────────────────────────────────────────────────
# Prerequisite checks
# ─────────────────────────────────────────────────────────────
if ! $SKIP_CHECKS; then
  echo "── Checking prerequisites... ──────────────────"
  PREFLIGHT_FAIL=0

  if ! command -v gcloud &>/dev/null; then
    echo "  ✗ gcloud CLI not found"; exit 1
  fi

  ACCOUNT=$(gcloud config get-value account 2>/dev/null)
  if [ -z "$ACCOUNT" ]; then
    echo "  ✗ Not authenticated. Run: gcloud auth login"; exit 1
  fi
  echo "  ✓ Authenticated as: ${ACCOUNT}"

  CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
  if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    gcloud config set project "$PROJECT_ID" --quiet
  fi
  echo "  ✓ Project: ${PROJECT_ID}"

  for secret in "GEMINI_API_KEY" "BLS_API_KEY" "FRED_API_KEY" "GOOGLE_MAPS_API_KEY" "FORGE_API_SECRET" "FORGE_V1_API_KEY" "CRON_SECRET" "RESEND_API_KEY"; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
      echo "  ✓ Secret: ${secret}"
    else
      echo "  ✗ Secret missing: ${secret}"
      PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
    fi
  done

  if [ $PREFLIGHT_FAIL -gt 0 ]; then
    echo "  ✗ ${PREFLIGHT_FAIL} prerequisite(s) missing."
    exit 1
  fi
  echo "  All prerequisites met."
  echo ""
fi

# ─────────────────────────────────────────────────────────────
# Build API image
# ─────────────────────────────────────────────────────────────
echo "──── Unified API Deploy ────────────────────────"
echo "  Project:   ${PROJECT_ID}"
echo "  Region:    ${REGION}"
echo "  Service:   ${API_SERVICE}"
echo "  Image:     ${API_IMAGE}"
echo "  Context:   ${REPO_ROOT}"
echo ""

echo "── Building FastAPI image..."
cat > /tmp/cloudbuild-unified-api.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${API_IMAGE}', '-f', 'infra/docker/Dockerfile.fastapi', '.']
images: ['${API_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-unified-api.yaml \
  --project "$PROJECT_ID" \
  --region "$BUILD_REGION" \
  --timeout=900 "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────
# Get crawl4ai URL (needed for API env var)
# ─────────────────────────────────────────────────────────────
CRAWL4AI_URL=$(gcloud run services describe "$CRAWL4AI_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)" 2>/dev/null || echo "")

# ─────────────────────────────────────────────────────────────
# Deploy API service
# ─────────────────────────────────────────────────────────────
echo "── Deploying API service (${API_SERVICE})..."

# Resolve the API's own URL for Cloud Tasks callbacks
EXISTING_API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)" 2>/dev/null || echo "")

ENV_VARS="PYTHONUNBUFFERED=1"
if [ -n "$EXISTING_API_URL" ]; then
  ENV_VARS="${ENV_VARS},API_BASE_URL=${EXISTING_API_URL}"
fi
if [ -n "$CRAWL4AI_URL" ]; then
  ENV_VARS="${ENV_VARS},CRAWL4AI_URL=${CRAWL4AI_URL}"
fi

RESEND_FROM_EMAIL="${RESEND_FROM_EMAIL:-onboarding@resend.dev}"
ENV_VARS="${ENV_VARS},RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL}"

gcloud run deploy "$API_SERVICE" \
  --image "$API_IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --concurrency 80 \
  --min-instances 1 \
  --max-instances 5 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "$ENV_VARS" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,BLS_API_KEY=BLS_API_KEY:latest,FRED_API_KEY=FRED_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest,CRON_SECRET=CRON_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,ADMIN_EMAIL_ALLOWLIST=ADMIN_EMAIL_ALLOWLIST:latest,MONITOR_NOTIFY_EMAILS=MONITOR_NOTIFY_EMAILS:latest" \
  --no-allow-unauthenticated

# Grant service account invoker role
gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" 2>/dev/null || true

API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")

echo ""
echo "══════════════════════════════════════════════"
echo "  ✓ API: ${API_URL}"
if [ -n "$CRAWL4AI_URL" ]; then
  echo "  ✓ crawl4ai: ${CRAWL4AI_URL}"
fi
echo "══════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────
# Cloud Scheduler: Workflow Monitor (every 30 min)
# ─────────────────────────────────────────────────────────────
MONITOR_JOB="workflow-monitor"
MONITOR_SCHEDULE="*/30 * * * *"
CRON_SECRET_VAL=$(gcloud secrets versions access latest --secret=CRON_SECRET --project="$PROJECT_ID" 2>/dev/null || echo "")

if [ -n "$CRON_SECRET_VAL" ] && [ -n "$API_URL" ]; then
  echo ""
  echo "── Setting up Workflow Monitor scheduler..."

  MONITOR_BASE_FLAGS=(
    --schedule "$MONITOR_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/workflow-monitor"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
  )

  if gcloud scheduler jobs describe "$MONITOR_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$MONITOR_JOB" "${MONITOR_BASE_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${MONITOR_JOB} (${MONITOR_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$MONITOR_JOB" "${MONITOR_BASE_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${MONITOR_JOB} (${MONITOR_SCHEDULE})"
  fi

  echo ""
  echo "  To change frequency:"
  echo "    gcloud scheduler jobs update http ${MONITOR_JOB} \\"
  echo "      --schedule '0 * * * *' \\"
  echo "      --location ${REGION} --project ${PROJECT_ID}"

  # --- Workflow Dispatcher (every 5 min) ---
  DISPATCHER_JOB="workflow-dispatcher"
  DISPATCHER_SCHEDULE="*/5 * * * *"

  DISPATCHER_BASE_FLAGS=(
    --schedule "$DISPATCHER_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/workflow-dispatcher"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
  )

  if gcloud scheduler jobs describe "$DISPATCHER_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$DISPATCHER_JOB" "${DISPATCHER_BASE_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${DISPATCHER_JOB} (${DISPATCHER_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$DISPATCHER_JOB" "${DISPATCHER_BASE_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${DISPATCHER_JOB} (${DISPATCHER_SCHEDULE})"
  fi
fi
