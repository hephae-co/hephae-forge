#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy admin frontend to Cloud Run
#
# Usage:
#   bash apps/admin/infra/deploy.sh
#   bash apps/admin/infra/deploy.sh --skip-checks
# ─────────────────────────────────────────────────────────────

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="us-central1"
BUILD_REGION="us-east1"
REPO="cloud-run-source-deploy"
TAG=$(git rev-parse --short HEAD)
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

ADMIN_SERVICE="hephae-admin-web"
API_SERVICE="hephae-forge-api"
ADMIN_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${ADMIN_SERVICE}:${TAG}"

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
# Build admin image
# ─────────────────────────────────────────────────────────────
echo "──── Admin Frontend Deploy ────────────────────────"
echo "  Service: ${ADMIN_SERVICE}"
echo "  Image:   ${ADMIN_IMAGE}"
echo ""

FIREBASE_API_KEY="${FIREBASE_API_KEY:?Set FIREBASE_API_KEY env var}"

echo "── Building Next.js image..."
cat > /tmp/cloudbuild-admin-web.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '--build-arg'
      - 'NEXT_PUBLIC_FIREBASE_API_KEY=${FIREBASE_API_KEY}'
      - '-t'
      - '${ADMIN_IMAGE}'
      - '-f'
      - 'apps/admin/infra/Dockerfile.nextjs'
      - '.'
images: ['${ADMIN_IMAGE}']
YAML
gcloud builds submit \
  --config /tmp/cloudbuild-admin-web.yaml \
  --project "$PROJECT_ID" \
  --region "$BUILD_REGION" \
  --timeout=600 "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────
# Get API URL from existing service (API is in us-east1)
# ─────────────────────────────────────────────────────────────
API_URL=$(gcloud run services describe "$API_SERVICE" \
  --region "us-east1" --project "$PROJECT_ID" \
  --format="value(status.url)")
echo "   ✓ API URL: ${API_URL}"

# ─────────────────────────────────────────────────────────────
# Deploy admin service
# ─────────────────────────────────────────────────────────────
echo "── Deploying Admin service (${ADMIN_SERVICE})..."
gcloud run deploy "$ADMIN_SERVICE" \
  --image "$ADMIN_IMAGE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --port 3000 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --concurrency 100 \
  --min-instances 0 \
  --max-instances 3 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "BACKEND_URL=${API_URL}"

ADMIN_URL=$(gcloud run services describe "$ADMIN_SERVICE" \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format "value(status.url)")

echo ""
echo "══════════════════════════════════════════════"
echo "  ✓ Admin: ${ADMIN_URL}"
echo "  ✓ API:   ${API_URL} (backend)"
echo "══════════════════════════════════════════════"
