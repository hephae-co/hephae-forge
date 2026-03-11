#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# deploy-discovery-job.sh — Deploy the discovery-batch Cloud Run Job
#                           + optional Cloud Scheduler trigger
#
# The job claims the next pending discovery job from Firestore and runs it
# to completion. Cloud Scheduler wakes it up on the configured cadence.
#
# Usage:
#   bash apps/api/infra/deploy-discovery-job.sh               # deploy job only
#   bash apps/api/infra/deploy-discovery-job.sh --schedule    # deploy + scheduler
#   bash apps/api/infra/deploy-discovery-job.sh --delete      # tear down all
#
# Scheduling:
#   Default schedule is daily at 2am ET (--schedule flag).
#   To change frequency later without redeploying:
#     gcloud scheduler jobs update http discovery-batch-trigger \
#       --schedule "0 2 * * 0" \   # weekly (Sunday 2am)
#       --project $GCP_PROJECT_ID
#
# Trigger manually:
#   gcloud run jobs execute discovery-batch --region us-central1 --project $GCP_PROJECT_ID --wait
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="us-central1"
JOB_NAME="discovery-batch"
SCHEDULER_JOB_NAME="${JOB_NAME}-trigger"
TAG=$(git rev-parse --short HEAD)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/hephae-forge-api:${TAG}"
SERVICE_ACCOUNT="hephae-forge@${PROJECT_ID}.iam.gserviceaccount.com"

# Cost-optimized: minimal resources, sequential processing
MEMORY="2Gi"
CPU="1"
# 8h — enough to process hundreds of businesses overnight
TASK_TIMEOUT="28800"

# Daily at 2am Eastern (UTC-5 in winter, UTC-4 in summer — use UTC-5 as safe default)
# Adjust with: gcloud scheduler jobs update http discovery-batch-trigger --schedule "..."
DEFAULT_SCHEDULE="0 7 * * *"   # 07:00 UTC = 02:00 ET

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }

# ──────────────────────────────────────────────────────────────────────────
# Parse flags
# ──────────────────────────────────────────────────────────────────────────
SETUP_SCHEDULER=false
DELETE=false
SCHEDULE="$DEFAULT_SCHEDULE"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --schedule)
            SETUP_SCHEDULER=true
            shift
            ;;
        --cron)
            if [[ -z "${2:-}" ]]; then echo "--cron requires a cron expression"; exit 1; fi
            SCHEDULE="$2"
            SETUP_SCHEDULER=true
            shift 2
            ;;
        --delete)
            DELETE=true
            shift
            ;;
        -h|--help)
            sed -n '2,14p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown flag: $1"; exit 1
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────────────────
if $DELETE; then
    info "Deleting Cloud Run Job: ${JOB_NAME}..."
    gcloud run jobs delete "$JOB_NAME" \
        --region "$REGION" --project "$PROJECT_ID" --quiet 2>/dev/null || true

    info "Deleting Cloud Scheduler job: ${SCHEDULER_JOB_NAME}..."
    gcloud scheduler jobs delete "$SCHEDULER_JOB_NAME" \
        --location "$REGION" --project "$PROJECT_ID" --quiet 2>/dev/null || true

    ok "Deleted."
    exit 0
fi

# ──────────────────────────────────────────────────────────────────────────
# Deploy Cloud Run Job
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── discovery-batch Cloud Run Job ────────────────${NC}"
echo "   Image:   ${IMAGE}"
echo "   CPU:     ${CPU} / Memory: ${MEMORY}"
echo "   Timeout: ${TASK_TIMEOUT}s ($(( TASK_TIMEOUT / 3600 ))h)"
echo ""

JOB_FLAGS=(
    --image "$IMAGE"
    --region "$REGION"
    --project "$PROJECT_ID"
    --service-account "$SERVICE_ACCOUNT"
    --memory "$MEMORY"
    --cpu "$CPU"
    --max-retries 1
    --task-timeout "$TASK_TIMEOUT"
    --set-env-vars "PYTHONPATH=/app:/app/apps/api,PYTHONUNBUFFERED=1,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},CLOUD_RUN_REGION=${REGION}"
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,RESEND_API_KEY=RESEND_API_KEY:latest"
    --command "python"
    --args "/app/apps/api/backend/run_discovery_batch.py"
)

if gcloud run jobs describe "$JOB_NAME" \
    --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    info "Updating existing job..."
    gcloud run jobs update "$JOB_NAME" "${JOB_FLAGS[@]}" --quiet
else
    info "Creating new job..."
    gcloud run jobs create "$JOB_NAME" "${JOB_FLAGS[@]}"
fi

ok "Cloud Run Job '${JOB_NAME}' ready."

# ──────────────────────────────────────────────────────────────────────────
# Cloud Scheduler (optional)
# ──────────────────────────────────────────────────────────────────────────
if $SETUP_SCHEDULER; then
    echo ""
    echo -e "${BOLD}── Cloud Scheduler ──────────────────────────────${NC}"
    echo "   Schedule: ${SCHEDULE}  (cron, UTC)"
    echo "   Job:      ${SCHEDULER_JOB_NAME}"
    echo ""

    # The scheduler executes the Cloud Run Job via its API
    JOB_RESOURCE="projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}"
    EXECUTE_URL="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"

    SCHEDULER_FLAGS=(
        --schedule "$SCHEDULE"
        --time-zone "America/New_York"
        --location "$REGION"
        --project "$PROJECT_ID"
        --uri "$EXECUTE_URL"
        --http-method POST
        --oauth-service-account-email "$SERVICE_ACCOUNT"
    )

    if gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" \
        --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
        info "Updating existing scheduler job..."
        gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" "${SCHEDULER_FLAGS[@]}" --quiet
    else
        info "Creating scheduler job..."
        gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" "${SCHEDULER_FLAGS[@]}"
    fi

    ok "Scheduler '${SCHEDULER_JOB_NAME}' set to: ${SCHEDULE} (America/New_York)"
    echo ""
    echo "  To change schedule frequency later (no redeploy needed):"
    echo "    gcloud scheduler jobs update http ${SCHEDULER_JOB_NAME} \\"
    echo "      --schedule '0 2 * * 0' \\"
    echo "      --location ${REGION} --project ${PROJECT_ID}"
    echo ""
    echo "  Examples:"
    echo "    Daily 2am ET:    '0 7 * * *'    (current)"
    echo "    Weekly Sunday:   '0 7 * * 0'"
    echo "    Twice a week:    '0 7 * * 0,3'"
    echo "    Every 12 hours:  '0 7,19 * * *'"
fi

echo ""
echo -e "${BOLD}── Manual trigger ───────────────────────────────${NC}"
echo "  gcloud run jobs execute ${JOB_NAME} \\"
echo "    --region ${REGION} --project ${PROJECT_ID} --wait"
echo ""
echo "  Or from the admin UI: Dashboard → Discovery Jobs → Run Now"
