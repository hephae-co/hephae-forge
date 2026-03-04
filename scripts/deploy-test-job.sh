#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Create / update the integration-tests Cloud Run Job
#
# Uses the same Docker image as hephae-forge, but overrides the
# entrypoint to run the test suite instead of supervisord.
#
# Usage:
#   ./scripts/deploy-test-job.sh           # create or update
#   ./scripts/deploy-test-job.sh --delete  # tear down the job
#
# After setup, trigger with:
#   ./scripts/trigger-cloud-tests.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
JOB_NAME="integration-tests"
TAG=$(git rev-parse --short HEAD)
IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/hephae-forge-api:${TAG}"
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

# Job resource limits
MEMORY="2Gi"
CPU="2"
TASK_TIMEOUT="900"  # 15 min — full suite can take a while

# ──────────────────────────────────────────────────────────────
# Parse flags
# ──────────────────────────────────────────────────────────────
DELETE=false
for arg in "$@"; do
    case "$arg" in
        --delete)
            DELETE=true
            ;;
        -h|--help)
            sed -n '2,14p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg"
            exit 1
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────
if $DELETE; then
    echo "Deleting Cloud Run Job: ${JOB_NAME}..."
    gcloud run jobs delete "$JOB_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --quiet
    echo "Deleted."
    exit 0
fi

# ──────────────────────────────────────────────────────────────
# Preflight
# ──────────────────────────────────────────────────────────────
echo "── Cloud Run Job: ${JOB_NAME} ──────────────────"
echo "   Image:   ${IMAGE}"
echo "   Region:  ${REGION}"
echo "   Account: ${SERVICE_ACCOUNT}"
echo "   Memory:  ${MEMORY} / ${CPU} CPU"
echo "   Timeout: ${TASK_TIMEOUT}s"
echo ""

# Common flags for create and update
JOB_FLAGS=(
    --image "$IMAGE"
    --region "$REGION"
    --project "$PROJECT_ID"
    --service-account "$SERVICE_ACCOUNT"
    --memory "$MEMORY"
    --cpu "$CPU"
    --max-retries 0
    --task-timeout "$TASK_TIMEOUT"
    --set-env-vars "PYTHONPATH=/app:/pylibs,NODE_ENV=test"
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
    --command "/bin/bash"
    --args "scripts/test-integration.sh,--report"
)

# ──────────────────────────────────────────────────────────────
# Create or update
# ──────────────────────────────────────────────────────────────
if gcloud run jobs describe "$JOB_NAME" \
    --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    echo "Updating existing job..."
    gcloud run jobs update "$JOB_NAME" "${JOB_FLAGS[@]}" --quiet
else
    echo "Creating new job..."
    gcloud run jobs create "$JOB_NAME" "${JOB_FLAGS[@]}"
fi

echo ""
echo "Job ready: ${JOB_NAME}"
echo ""
echo "Trigger with:  ./scripts/trigger-cloud-tests.sh"
echo "Or directly:   gcloud run jobs execute ${JOB_NAME} --region ${REGION} --wait"
