#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# deploy-eval-job.sh — Create / update the agent-evals Cloud Run Job
#
# The job runs ADK agent evaluations against the full capability stack
# using the same Docker image as the unified API.
#
# Usage:
#   bash apps/api/infra/deploy-eval-job.sh             # create or update
#   bash apps/api/infra/deploy-eval-job.sh --delete    # tear down the job
#
# After deploy, trigger with:
#   bash apps/api/infra/trigger-evals.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
JOB_NAME="agent-evals"
TAG=$(git rev-parse --short HEAD)
IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/hephae-forge-api:${TAG}"
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

# Resources — ADK evals do real LLM + tool calls per test case
MEMORY="4Gi"
CPU="2"
# 7 agents × ~5 min each + buffer = 45 min
TASK_TIMEOUT="2700"

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
            sed -n '2,12p' "$0" | sed 's/^# \?//'
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
echo "   Image:    ${IMAGE}"
echo "   Region:   ${REGION}"
echo "   Account:  ${SERVICE_ACCOUNT}"
echo "   Memory:   ${MEMORY} / ${CPU} CPU"
echo "   Timeout:  ${TASK_TIMEOUT}s ($(( TASK_TIMEOUT / 60 )) min)"
echo ""

# PYTHONPATH must include:
#   /app/apps/api — for backend.* imports
#   /app          — for tests.* imports
PYTHONPATH_VAL="/app:/app/apps/api"

JOB_FLAGS=(
    --image "$IMAGE"
    --region "$REGION"
    --project "$PROJECT_ID"
    --service-account "$SERVICE_ACCOUNT"
    --memory "$MEMORY"
    --cpu "$CPU"
    --max-retries 0
    --task-timeout "$TASK_TIMEOUT"
    --set-env-vars "PYTHONPATH=${PYTHONPATH_VAL},PYTHONUNBUFFERED=1,EVAL_MODE=static"
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest"
    --command "python"
    --args "/app/tests/evals/run_all.py"
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
echo "Run all evals:           bash apps/api/infra/trigger-evals.sh"
echo "Run a specific agent:    bash apps/api/infra/trigger-evals.sh --agent seo_auditor"
echo "Run human-curated only:  bash apps/api/infra/trigger-evals.sh --human-curated"
