#!/bin/bash
set -e

# Configuration
PROJECT_ID="hephae-co-dev"
REGION="us-central1"
SERVICE_NAME="hephae-admin"
REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"
IMAGE="${REPO}/${SERVICE_NAME}"
TAG="$(git rev-parse --short HEAD)"

# ── Load .env ──
if [ -f .env ]; then
    echo "Loading .env file..."
    while IFS='=' read -r key value; do
        [[ -z "$key" || "$key" == \#* ]] && continue
        if [ -z "${!key}" ]; then
            export "$key=$value"
        fi
    done < .env
fi

# ── Validate ──
REQUIRED_VARS=(FORGE_URL RESEND_API_KEY)
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
    [ -z "${!var}" ] && MISSING+=("$var")
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "ERROR: Missing: ${MISSING[*]}"
    exit 1
fi

echo "====================================================="
echo " Fast Deploy: Cloud Build with layer cache"
echo "====================================================="
echo "  Image:   ${IMAGE}:${TAG}"
echo "  Service: ${SERVICE_NAME}"
echo ""

# ── Step 1: Build with kaniko cache via Cloud Build ──
echo "[1/2] Building image with Cloud Build (cached layers)..."
gcloud builds submit \
  --project $PROJECT_ID \
  --region $REGION \
  --tag "${IMAGE}:${TAG}" \
  --gcs-log-dir="gs://${PROJECT_ID}_cloudbuild/logs" \
  .

# ── Step 2: Deploy the pre-built image (skip source build) ──
echo ""
echo "[2/2] Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image "${IMAGE}:${TAG}" \
  --project $PROJECT_ID \
  --region $REGION \
  --allow-unauthenticated \
  --timeout=3600 \
  --set-env-vars="\
FORGE_URL=${FORGE_URL},\
RESEND_API_KEY=${RESEND_API_KEY},\
RESEND_FROM_EMAIL=${RESEND_FROM_EMAIL:-onboarding@resend.dev},\
CRON_SECRET=${CRON_SECRET:-hephae_cron_secret}" \
  --set-secrets="GOOGLE_GENAI_API_KEY=GOOGLE_GENAI_API_KEY:latest,FORGE_API_SECRET=FORGE_API_SECRET:latest,FORGE_V1_API_KEY=FORGE_V1_API_KEY:latest"

echo ""
echo "====================================================="
echo " Deployed ${TAG} successfully!"
echo "====================================================="
echo " Service URL: https://${SERVICE_NAME}-$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)').${REGION}.run.app"
