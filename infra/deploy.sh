#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy Hephae Forge
#
# Usage:
#   ./infra/deploy.sh                  # Build + deploy web + API only
#   ./infra/deploy.sh --with-crawl4ai  # Also rebuild + redeploy crawl4ai
#   ./infra/deploy.sh --skip-checks    # Skip prerequisite verification
# ─────────────────────────────────────────────────────────────

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
REPO="cloud-run-source-deploy"
TAG=$(git rev-parse --short HEAD)
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

# Service names
WEB_SERVICE="hephae-forge-web"
API_SERVICE="hephae-forge-api"
CRAWL4AI_SERVICE="hephae-crawl4ai"

# Image names
WEB_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${WEB_SERVICE}:${TAG}"
API_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${API_SERVICE}:${TAG}"
CRAWL4AI_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${CRAWL4AI_SERVICE}:latest"

# Cloud Run config
TIMEOUT="300"
MAX_INSTANCES="5"
MIN_INSTANCES="0"

# ─────────────────────────────────────────────────────────────
# Parse flags
# ─────────────────────────────────────────────────────────────
SKIP_CHECKS=false
WITH_CRAWL4AI=false
for arg in "$@"; do
  case $arg in
    --skip-checks) SKIP_CHECKS=true ;;
    --with-crawl4ai) WITH_CRAWL4AI=true ;;
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

  if gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ✓ Service account: ${SERVICE_ACCOUNT}"
  else
    echo "  ✗ Service account missing: ${SERVICE_ACCOUNT}"
    PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
  fi

  for secret in "GEMINI_API_KEY" "BLS_API_KEY" "FRED_API_KEY" "GOOGLE_MAPS_API_KEY" "FORGE_API_SECRET" "FORGE_V1_API_KEY"; do
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
# 1. Build images
# ─────────────────────────────────────────────────────────────
echo "──── Hephae Forge Deploy ────────────────────────"
echo "  Project:   ${PROJECT_ID}"
echo "  Region:    ${REGION}"
echo "  Web:       ${WEB_SERVICE} → ${WEB_IMAGE}"
echo "  API:       ${API_SERVICE} → ${API_IMAGE}"
if $WITH_CRAWL4AI; then
  echo "  crawl4ai:  ${CRAWL4AI_SERVICE} → ${CRAWL4AI_IMAGE} (rebuild)"
else
  echo "  crawl4ai:  ${CRAWL4AI_SERVICE} (skipped — already deployed)"
fi
echo ""

echo "── Building Next.js image..."
cat > /tmp/cloudbuild-web.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${WEB_IMAGE}', '-f', 'infra/Dockerfile.nextjs', '.']
images: ['${WEB_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-web.yaml \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --timeout=600 .

echo "── Building FastAPI image..."
cat > /tmp/cloudbuild-api.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${API_IMAGE}', '-f', 'infra/Dockerfile.fastapi', '.']
images: ['${API_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-api.yaml \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --timeout=900 .

if $WITH_CRAWL4AI; then
  echo "── Mirroring crawl4ai image to Artifact Registry..."
  cat > /tmp/cloudbuild-crawl4ai.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['pull', 'unclecode/crawl4ai:latest']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['tag', 'unclecode/crawl4ai:latest', '${CRAWL4AI_IMAGE}']
images: ['${CRAWL4AI_IMAGE}']
YAML
  gcloud builds submit \
    --config /tmp/cloudbuild-crawl4ai.yaml \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --no-source \
    --timeout=300

  # ─────────────────────────────────────────────────────────────
  # Deploy crawl4ai service (web scraper — unauthenticated)
  # ─────────────────────────────────────────────────────────────
  echo "── Deploying crawl4ai service (${CRAWL4AI_SERVICE})..."
  gcloud run deploy "$CRAWL4AI_SERVICE" \
    --image "$CRAWL4AI_IMAGE" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --platform managed \
    --port 11235 \
    --memory 2Gi \
    --cpu 2 \
    --timeout "$TIMEOUT" \
    --min-instances 0 \
    --max-instances 3 \
    --service-account "$SERVICE_ACCOUNT" \
    --allow-unauthenticated
  echo "   ✓ crawl4ai rebuilt + deployed"
else
  echo "── Skipping crawl4ai (use --with-crawl4ai to rebuild)"
fi

# Get crawl4ai URL from existing service (needed for API env var)
CRAWL4AI_URL=$(gcloud run services describe "$CRAWL4AI_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "   ✓ crawl4ai: ${CRAWL4AI_URL}"

# ─────────────────────────────────────────────────────────────
# 3. Deploy API service (backend — internal only, no public access)
# ─────────────────────────────────────────────────────────────
echo "── Deploying API service (${API_SERVICE})..."
gcloud run deploy "$API_SERVICE" \
  --image "$API_IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --port 8000 \
  --memory 2Gi \
  --cpu 2 \
  --timeout "$TIMEOUT" \
  --min-instances 1 \
  --max-instances "$MAX_INSTANCES" \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "PYTHONUNBUFFERED=1,CRAWL4AI_URL=${CRAWL4AI_URL}" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,BLS_API_KEY=BLS_API_KEY:latest,FRED_API_KEY=FRED_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest" \
  --no-allow-unauthenticated

# Get the API service URL for the frontend to use
API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "   ✓ API deployed: ${API_URL}"

# Grant the web service's SA permission to call the API service
gcloud run services add-iam-policy-binding "$API_SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" 2>/dev/null || true

# ─────────────────────────────────────────────────────────────
# 4. Deploy Web service (frontend — public)
# ─────────────────────────────────────────────────────────────
echo "── Deploying Web service (${WEB_SERVICE})..."
gcloud run deploy "$WEB_SERVICE" \
  --image "$WEB_IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --port 3000 \
  --memory 512Mi \
  --cpu 1 \
  --timeout "$TIMEOUT" \
  --min-instances "$MIN_INSTANCES" \
  --max-instances "$MAX_INSTANCES" \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "NODE_ENV=production,BACKEND_URL=${API_URL}" \
  --set-secrets "FORGE_API_SECRET=FORGE_API_SECRET:latest" \
  --allow-unauthenticated

WEB_URL=$(gcloud run services describe "$WEB_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")

echo ""
echo "══════════════════════════════════════════════"
echo "  ✓ Web:      ${WEB_URL}"
echo "  ✓ API:      ${API_URL} (internal)"
echo "  ✓ crawl4ai: ${CRAWL4AI_URL}"
echo "══════════════════════════════════════════════"
