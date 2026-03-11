#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy web frontend to Cloud Run
#
# Usage:
#   bash apps/web/infra/deploy.sh
#   bash apps/web/infra/deploy.sh --skip-checks
# ─────────────────────────────────────────────────────────────

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="us-central1"
REPO="cloud-run-source-deploy"
TAG=$(git rev-parse --short HEAD)
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

WEB_SERVICE="hephae-forge-web"
API_SERVICE="hephae-forge-api"
WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${WEB_SERVICE}:${TAG}"

# Resolve repo root (build context must be monorepo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

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
  echo ""
fi

# ─────────────────────────────────────────────────────────────
# Build web image
# ─────────────────────────────────────────────────────────────
echo "──── Web Frontend Deploy ────────────────────────"
echo "  Service: ${WEB_SERVICE}"
echo "  Image:   ${WEB_IMAGE}"
echo ""

FIREBASE_API_KEY="${FIREBASE_API_KEY:?Set FIREBASE_API_KEY env var}"

echo "── Building Next.js image..."
cat > /tmp/cloudbuild-web.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '--build-arg'
      - 'NEXT_PUBLIC_FIREBASE_API_KEY=${FIREBASE_API_KEY}'
      - '-t'
      - '${WEB_IMAGE}'
      - '-f'
      - 'apps/web/infra/Dockerfile.nextjs'
      - '.'
images: ['${WEB_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-web.yaml \
  --project "$PROJECT_ID" \
  --region "${BUILD_REGION:-$REGION}" \
  --timeout=600 "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────
# Get API URL from existing service
# ─────────────────────────────────────────────────────────────
API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "   ✓ API URL: ${API_URL}"

# ─────────────────────────────────────────────────────────────
# Deploy web service
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
  --timeout 300 \
  --min-instances 0 \
  --max-instances 5 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "NODE_ENV=production,BACKEND_URL=${API_URL}" \
  --set-secrets "FORGE_API_SECRET=FORGE_API_SECRET:latest" \
  --allow-unauthenticated

WEB_URL=$(gcloud run services describe "$WEB_SERVICE" \
  --region "$REGION" --project "$PROJECT_ID" \
  --format="value(status.url)")

echo ""
echo "══════════════════════════════════════════════"
echo "  ✓ Web: ${WEB_URL}"
echo "  ✓ API: ${API_URL} (backend)"
echo "══════════════════════════════════════════════"
