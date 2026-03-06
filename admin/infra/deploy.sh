#!/bin/bash
set -euo pipefail

# Deploy hephae-admin to Google Cloud Run (2 services)
# Usage: bash infra/deploy.sh

PROJECT_ID="hephae-co-dev"
REGION="us-central1"
REPO="cloud-run-source-deploy"
TAG=$(git rev-parse --short HEAD)
API_SERVICE="hephae-admin-api"
WEB_SERVICE="hephae-admin-web"

# Image names
API_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${API_SERVICE}:${TAG}"
WEB_IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${WEB_SERVICE}:${TAG}"

# Resolve repo root (build context must be monorepo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Deploying hephae-admin (2-service architecture) ==="

# Validate required env vars
for var in FORGE_URL RESEND_API_KEY; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set"
        exit 1
    fi
done

# --- API Service ---
echo "--- Building API image ---"
cat > /tmp/cloudbuild-admin-api.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${API_IMAGE}', '-f', 'admin/infra/Dockerfile.fastapi', '.']
images: ['${API_IMAGE}']
YAML
gcloud builds submit \
    --config /tmp/cloudbuild-admin-api.yaml \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --timeout=600 "$REPO_ROOT"

echo "--- Deploying API service ---"
gcloud run deploy "${API_SERVICE}" \
    --image "$API_IMAGE" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "FORGE_URL=${FORGE_URL}" \
    --set-env-vars "RESEND_API_KEY=${RESEND_API_KEY}" \
    --set-env-vars "RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL:-onboarding@resend.dev}" \
    --set-env-vars "CRON_SECRET=${CRON_SECRET:-}" \
    --set-secrets "GEMINI_API_KEY=GOOGLE_GENAI_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest"

# Get API URL
API_URL=$(gcloud run services describe "${API_SERVICE}" \
    --platform managed \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format "value(status.url)")

echo "API deployed at: ${API_URL}"

# --- Web Service ---
echo "--- Building Web image ---"
cat > /tmp/cloudbuild-admin-web.yaml <<YAML
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${WEB_IMAGE}', '-f', 'admin/infra/Dockerfile.nextjs', '.']
images: ['${WEB_IMAGE}']
YAML
gcloud builds submit \
    --config /tmp/cloudbuild-admin-web.yaml \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --timeout=600 "$REPO_ROOT"

echo "--- Deploying Web service ---"
gcloud run deploy "${WEB_SERVICE}" \
    --image "$WEB_IMAGE" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --concurrency 100 \
    --min-instances 0 \
    --max-instances 3 \
    --set-env-vars "BACKEND_URL=${API_URL}"

WEB_URL=$(gcloud run services describe "${WEB_SERVICE}" \
    --platform managed \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format "value(status.url)")

echo ""
echo "=== Deployment Complete ==="
echo "API: ${API_URL}"
echo "Web: ${WEB_URL}"
