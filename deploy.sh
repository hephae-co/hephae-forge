#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# deploy.sh — Build & deploy Hephae Forge to Cloud Run
#
# Usage:
#   ./deploy.sh               # Full build + deploy
#   ./deploy.sh --build-only  # Just build the image, don't deploy
#   ./deploy.sh --deploy-only # Just deploy (image must already exist)
#   ./deploy.sh --skip-checks # Skip prerequisite verification
#
# Prerequisites: run ./setup.sh first (or ./setup.sh --check-only to verify)
# ─────────────────────────────────────────────────────────────

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
SERVICE_NAME="hephae-forge"
REPO="hephae-docker"
IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"
TAG="${IMAGE}:$(git rev-parse --short HEAD)"
LATEST="${IMAGE}:latest"
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

# Cloud Run service config
MEMORY="2Gi"
CPU="2"
MAX_INSTANCES="5"
MIN_INSTANCES="0"
TIMEOUT="300"                                  # 5 min — agents can be slow
PORT="3000"

# ─────────────────────────────────────────────────────────────
# Parse flags
# ─────────────────────────────────────────────────────────────
BUILD=true
DEPLOY=true
SKIP_CHECKS=false

for arg in "$@"; do
  case $arg in
    --build-only)   DEPLOY=false ;;
    --deploy-only)  BUILD=false ;;
    --skip-checks)  SKIP_CHECKS=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ─────────────────────────────────────────────────────────────
# Prerequisite checks
# ─────────────────────────────────────────────────────────────
if ! $SKIP_CHECKS; then
  echo "── Checking prerequisites... ──────────────────"
  PREFLIGHT_FAIL=0

  # gcloud installed
  if ! command -v gcloud &>/dev/null; then
    echo "  ✗ gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
    exit 1
  fi

  # Authenticated
  ACCOUNT=$(gcloud config get-value account 2>/dev/null)
  if [ -z "$ACCOUNT" ]; then
    echo "  ✗ Not authenticated. Run: gcloud auth login"
    exit 1
  fi
  echo "  ✓ Authenticated as: ${ACCOUNT}"

  # Correct project
  CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
  if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo "  ⚠ Switching project to ${PROJECT_ID}..."
    gcloud config set project "$PROJECT_ID" --quiet
  fi
  echo "  ✓ Project: ${PROJECT_ID}"

  # Service account exists
  if gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ✓ Service account: ${SERVICE_ACCOUNT}"
  else
    echo "  ✗ Service account missing: ${SERVICE_ACCOUNT}"
    PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
  fi

  # Required secrets exist with active versions
  for secret in "GEMINI_API_KEY" "BLS_API_KEY" "FRED_API_KEY" "GOOGLE_MAPS_API_KEY"; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
      VERSION_COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
        --format="value(name)" --filter="state=ENABLED" 2>/dev/null | wc -l | tr -d ' ')
      if [ "$VERSION_COUNT" -gt 0 ]; then
        echo "  ✓ Secret: ${secret}"
      else
        echo "  ✗ Secret ${secret} exists but has no enabled versions"
        PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
      fi
    else
      echo "  ✗ Secret missing: ${secret}"
      PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
    fi
  done

  # Artifact Registry repo exists
  if gcloud artifacts repositories describe "$REPO" \
      --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ✓ Artifact Registry: ${REPO}"
  else
    echo "  ✗ Artifact Registry repo missing: ${REPO}"
    PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
  fi

  # Required APIs
  ENABLED_APIS=$(gcloud services list --enabled --format="value(config.name)" --project="$PROJECT_ID" 2>/dev/null)
  for api in "run.googleapis.com" "cloudbuild.googleapis.com" "artifactregistry.googleapis.com" "secretmanager.googleapis.com"; do
    if echo "$ENABLED_APIS" | grep -q "^${api}$"; then
      echo "  ✓ API: ${api}"
    else
      echo "  ✗ API not enabled: ${api}"
      PREFLIGHT_FAIL=$((PREFLIGHT_FAIL + 1))
    fi
  done

  echo ""

  if [ $PREFLIGHT_FAIL -gt 0 ]; then
    echo "══════════════════════════════════════════════"
    echo "  ✗ ${PREFLIGHT_FAIL} prerequisite(s) missing."
    echo "  Run ./setup.sh to fix, or --skip-checks to bypass."
    echo "══════════════════════════════════════════════"
    exit 1
  fi
  echo "  All prerequisites met."
  echo ""
fi

# ─────────────────────────────────────────────────────────────
# Deploy banner
# ─────────────────────────────────────────────────────────────
echo "──── Hephae Forge Deploy ─────────────────────"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${TAG}"
echo ""

# ─────────────────────────────────────────────────────────────
# 1. Build with Cloud Build
# ─────────────────────────────────────────────────────────────
if $BUILD; then
  echo "── Building image via Cloud Build..."
  gcloud builds submit \
    --tag "$TAG" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --timeout=1200

  # Also tag as :latest
  echo "── Tagging as :latest..."
  gcloud artifacts docker tags add "$TAG" "$LATEST" 2>/dev/null || true
  echo "   ✓ Image built: ${TAG}"
  echo ""
fi

# ─────────────────────────────────────────────────────────────
# 2. Deploy to Cloud Run
# ─────────────────────────────────────────────────────────────
if $DEPLOY; then
  echo "── Deploying to Cloud Run..."
  gcloud run deploy "$SERVICE_NAME" \
    --image "$LATEST" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --platform managed \
    --port "$PORT" \
    --memory "$MEMORY" \
    --cpu "$CPU" \
    --timeout "$TIMEOUT" \
    --min-instances "$MIN_INSTANCES" \
    --max-instances "$MAX_INSTANCES" \
    --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "NODE_ENV=production,CRAWL4AI_URL=http://localhost:11235,PYTHONPATH=/app:/pylibs" \
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,BLS_API_KEY=BLS_API_KEY:latest,FRED_API_KEY=FRED_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest" \
    --allow-unauthenticated

  # Print the service URL
  URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format="value(status.url)")
  echo ""
  echo "══════════════════════════════════════════════"
  echo "  ✓ Deployed: ${URL}"
  echo "══════════════════════════════════════════════"
  echo ""
  echo "Next: update ADMIN_APP_API.md base URL with this URL."
fi
