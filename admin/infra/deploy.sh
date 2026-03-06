#!/bin/bash
set -euo pipefail

# Deploy hephae-admin to Google Cloud Run (2 services)
# Usage: bash infra/deploy.sh

PROJECT_ID="hephae-co-dev"
REGION="us-central1"
API_SERVICE="hephae-admin-api"
WEB_SERVICE="hephae-admin-web"

echo "=== Deploying hephae-admin (2-service architecture) ==="

# Validate required env vars
for var in FORGE_URL RESEND_API_KEY; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set"
        exit 1
    fi
done

# --- API Service ---
# Temporarily copy Dockerfile to root for gcloud run deploy --source
echo "--- Building & deploying API service ---"
cp infra/Dockerfile.fastapi Dockerfile
gcloud run deploy "${API_SERVICE}" \
    --source . \
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
rm -f Dockerfile

# Get API URL
API_URL=$(gcloud run services describe "${API_SERVICE}" \
    --platform managed \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format "value(status.url)")

echo "API deployed at: ${API_URL}"

# --- Web Service ---
echo "--- Building & deploying Web service ---"
cp infra/Dockerfile.nextjs Dockerfile
gcloud run deploy "${WEB_SERVICE}" \
    --source . \
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
rm -f Dockerfile

WEB_URL=$(gcloud run services describe "${WEB_SERVICE}" \
    --platform managed \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --format "value(status.url)")

echo ""
echo "=== Deployment Complete ==="
echo "API: ${API_URL}"
echo "Web: ${WEB_URL}"
