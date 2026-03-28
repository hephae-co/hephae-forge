#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy API service + batch job to Cloud Run
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

BATCH_JOB="hephae-forge-batch"
BATCH_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${BATCH_JOB}:${TAG}"

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
# Build API image (lightweight — no Playwright)
# ─────────────────────────────────────────────────────────────
echo "──── API Service Deploy ─────────────────────────"
echo "  Project:   ${PROJECT_ID}"
echo "  Region:    ${REGION}"
echo "  Service:   ${API_SERVICE}"
echo "  Image:     ${API_IMAGE}"
echo ""

echo "── Building API image (lightweight, no Playwright)..."
cat > /tmp/cloudbuild-api.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${API_IMAGE}', '-f', 'infra/docker/Dockerfile.api', '.']
images: ['${API_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-api.yaml \
  --project "$PROJECT_ID" \
  --region "$BUILD_REGION" \
  --timeout=900 "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────
# Deploy API service (lightweight interactive)
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

RESEND_FROM_EMAIL="${RESEND_FROM_EMAIL:-hello@info.hephae.co}"
ENV_VARS="${ENV_VARS},RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL}"

gcloud run deploy "$API_SERVICE" \
  --image "$API_IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --port 8080 \
  --memory 1Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 1 \
  --max-instances 5 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "$ENV_VARS" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,BLS_API_KEY=BLS_API_KEY:latest,FRED_API_KEY=FRED_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest,CRON_SECRET=CRON_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,ADMIN_EMAIL_ALLOWLIST=ADMIN_EMAIL_ALLOWLIST:latest,MONITOR_NOTIFY_EMAILS=MONITOR_NOTIFY_EMAILS:latest,USDA_NASS_API_KEY=USDA_NASS_API_KEY:latest,USDA_FDC_API_KEY=USDA_FDC_API_KEY:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
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
echo "══════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────
# Build Batch image (heavy — with Playwright)
# ─────────────────────────────────────────────────────────────
echo ""
echo "──── Batch Job Deploy ─────────────────────────"
echo "  Job:       ${BATCH_JOB}"
echo "  Image:     ${BATCH_IMAGE}"
echo ""

echo "── Building batch image (with Playwright)..."
cat > /tmp/cloudbuild-batch.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${BATCH_IMAGE}', '-f', 'infra/docker/Dockerfile.batch', '.']
images: ['${BATCH_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-batch.yaml \
  --project "$PROJECT_ID" \
  --region "$BUILD_REGION" \
  --timeout=1200 "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────
# Deploy Batch Cloud Run Job
# ─────────────────────────────────────────────────────────────
echo "── Deploying batch job (${BATCH_JOB})..."

BATCH_ENV_VARS="PYTHONUNBUFFERED=1"
if [ -n "$API_URL" ]; then
  BATCH_ENV_VARS="${BATCH_ENV_VARS},API_BASE_URL=${API_URL}"
fi
BATCH_ENV_VARS="${BATCH_ENV_VARS},RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL}"

BATCH_SECRETS="GEMINI_API_KEY=GEMINI_API_KEY:latest,BLS_API_KEY=BLS_API_KEY:latest,FRED_API_KEY=FRED_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest,CRON_SECRET=CRON_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,ADMIN_EMAIL_ALLOWLIST=ADMIN_EMAIL_ALLOWLIST:latest,MONITOR_NOTIFY_EMAILS=MONITOR_NOTIFY_EMAILS:latest,USDA_NASS_API_KEY=USDA_NASS_API_KEY:latest,USDA_FDC_API_KEY=USDA_FDC_API_KEY:latest"

# Create or update the Cloud Run Job
if gcloud run jobs describe "$BATCH_JOB" \
    --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
  gcloud run jobs update "$BATCH_JOB" \
    --image "$BATCH_IMAGE" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --memory 4Gi \
    --cpu 2 \
    --task-timeout 3600 \
    --max-retries 1 \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "$BATCH_ENV_VARS" \
    --set-secrets "$BATCH_SECRETS"
  echo "  ✓ Updated job: ${BATCH_JOB}"
else
  gcloud run jobs create "$BATCH_JOB" \
    --image "$BATCH_IMAGE" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --memory 4Gi \
    --cpu 2 \
    --task-timeout 3600 \
    --max-retries 1 \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "$BATCH_ENV_VARS" \
    --set-secrets "$BATCH_SECRETS"
  echo "  ✓ Created job: ${BATCH_JOB}"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  ✓ API:   ${API_URL} (1Gi, 2 vCPU)"
echo "  ✓ Batch: ${BATCH_JOB} (4Gi, 2 vCPU, scale-to-zero)"
echo "  ℹ crawl4ai: ephemeral (spun up per-job)"
echo "══════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────
# Cloud Scheduler: Pulse & Intelligence Crons
# ─────────────────────────────────────────────────────────────
CRON_SECRET_VAL=$(gcloud secrets versions access latest --secret=CRON_SECRET --project="$PROJECT_ID" 2>/dev/null || echo "")

if [ -n "$CRON_SECRET_VAL" ] && [ -n "$API_URL" ]; then
  # --- Weekly Pulse Cron (Saturday 5am ET) ---
  PULSE_CRON_JOB="weekly-pulse-cron"
  PULSE_CRON_SCHEDULE="0 5 * * 6"
  PULSE_CRON_FLAGS=(
    --schedule "$PULSE_CRON_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/weekly-pulse"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
    --attempt-deadline "30m"
  )
  if gcloud scheduler jobs describe "$PULSE_CRON_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$PULSE_CRON_JOB" "${PULSE_CRON_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${PULSE_CRON_JOB} (${PULSE_CRON_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$PULSE_CRON_JOB" "${PULSE_CRON_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${PULSE_CRON_JOB} (${PULSE_CRON_SCHEDULE})"
  fi

  # --- Tech Intelligence Cron (Saturday 1am ET) ---
  TECH_INTEL_JOB="tech-intelligence-cron"
  TECH_INTEL_SCHEDULE="0 1 * * 6"
  TECH_INTEL_FLAGS=(
    --schedule "$TECH_INTEL_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/tech-intelligence"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
    --attempt-deadline "30m"
  )
  if gcloud scheduler jobs describe "$TECH_INTEL_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$TECH_INTEL_JOB" "${TECH_INTEL_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${TECH_INTEL_JOB} (${TECH_INTEL_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$TECH_INTEL_JOB" "${TECH_INTEL_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${TECH_INTEL_JOB} (${TECH_INTEL_SCHEDULE})"
  fi

  # --- Industry Pulse Cron (Saturday 3am ET) ---
  INDUSTRY_PULSE_JOB="industry-pulse-cron"
  INDUSTRY_PULSE_SCHEDULE="0 3 * * 6"
  INDUSTRY_PULSE_FLAGS=(
    --schedule "$INDUSTRY_PULSE_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/industry-pulse"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
    --attempt-deadline "30m"
  )
  if gcloud scheduler jobs describe "$INDUSTRY_PULSE_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$INDUSTRY_PULSE_JOB" "${INDUSTRY_PULSE_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${INDUSTRY_PULSE_JOB} (${INDUSTRY_PULSE_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$INDUSTRY_PULSE_JOB" "${INDUSTRY_PULSE_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${INDUSTRY_PULSE_JOB} (${INDUSTRY_PULSE_SCHEDULE})"
  fi

  # --- Reference Harvest Cron (Saturday 9am ET) ---
  REF_HARVEST_JOB="reference-harvest-cron"
  REF_HARVEST_SCHEDULE="0 9 * * 6"
  REF_HARVEST_FLAGS=(
    --schedule "$REF_HARVEST_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/reference-harvest"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
    --attempt-deadline "30m"
  )
  if gcloud scheduler jobs describe "$REF_HARVEST_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$REF_HARVEST_JOB" "${REF_HARVEST_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${REF_HARVEST_JOB} (${REF_HARVEST_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$REF_HARVEST_JOB" "${REF_HARVEST_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${REF_HARVEST_JOB} (${REF_HARVEST_SCHEDULE})"
  fi

  # --- AI Tool Discovery Cron (Saturday 7am ET) ---
  AI_TOOL_JOB="ai-tool-discovery-cron"
  AI_TOOL_SCHEDULE="0 7 * * 6"
  AI_TOOL_FLAGS=(
    --schedule "$AI_TOOL_SCHEDULE"
    --time-zone "America/New_York"
    --location "$REGION"
    --project "$PROJECT_ID"
    --uri "${API_URL}/api/cron/ai-tool-discovery"
    --http-method GET
    --oidc-service-account-email "$SERVICE_ACCOUNT"
    --attempt-deadline "30m"
  )
  if gcloud scheduler jobs describe "$AI_TOOL_JOB" \
      --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    gcloud scheduler jobs update http "$AI_TOOL_JOB" "${AI_TOOL_FLAGS[@]}" \
      --update-headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}" --quiet
    echo "  ✓ Updated scheduler: ${AI_TOOL_JOB} (${AI_TOOL_SCHEDULE})"
  else
    gcloud scheduler jobs create http "$AI_TOOL_JOB" "${AI_TOOL_FLAGS[@]}" \
      --headers "X-Cron-Secret=Bearer ${CRON_SECRET_VAL}"
    echo "  ✓ Created scheduler: ${AI_TOOL_JOB} (${AI_TOOL_SCHEDULE})"
  fi
fi
