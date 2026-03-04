#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Trigger integration tests on Cloud Run and show report URL
#
# Usage:
#   ./scripts/trigger-cloud-tests.sh           # run all levels
#   ./scripts/trigger-cloud-tests.sh --status   # check last execution
#
# Prerequisites:
#   1. Deploy the app:        ./infra/deploy.sh
#   2. Create the test job:   ./scripts/deploy-test-job.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
JOB_NAME="integration-tests"
BUCKET="everything-hephae"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()   { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()     { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()   { echo -e "${YELLOW}[WARN]${NC}  $*"; }

# ──────────────────────────────────────────────────────────────
# Parse flags
# ──────────────────────────────────────────────────────────────
STATUS_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --status)
            STATUS_ONLY=true
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
# --status: show last execution info
# ──────────────────────────────────────────────────────────────
if $STATUS_ONLY; then
    echo -e "${BOLD}── Last execution ──${NC}"
    gcloud run jobs executions list \
        --job "$JOB_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --limit 5 \
        --format "table(name, createTime.date(), status.completionTime.date(), status.succeededCount, status.failedCount)"

    echo ""
    info "View logs: gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --project ${PROJECT_ID} --limit 50 --format 'value(textPayload)'"
    echo ""

    # Find latest report in GCS
    LATEST_REPORT=$(gcloud storage ls "gs://${BUCKET}/test-reports/" 2>/dev/null | sort | tail -1)
    if [[ -n "$LATEST_REPORT" ]]; then
        # Convert gs:// path to https:// URL
        REPORT_PATH="${LATEST_REPORT}report.html"
        REPORT_URL="${REPORT_PATH/gs:\/\/${BUCKET}/https:\/\/storage.googleapis.com\/${BUCKET}}"
        ok "Latest report: ${REPORT_URL}"
    fi
    exit 0
fi

# ──────────────────────────────────────────────────────────────
# Verify job exists
# ──────────────────────────────────────────────────────────────
if ! gcloud run jobs describe "$JOB_NAME" \
    --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    echo -e "${RED}Job '${JOB_NAME}' not found.${NC}"
    echo "Create it first: ./scripts/deploy-test-job.sh"
    exit 1
fi

# ──────────────────────────────────────────────────────────────
# Update image to latest (pick up newly deployed code)
# ──────────────────────────────────────────────────────────────
IMAGE="us-east1-docker.pkg.dev/${PROJECT_ID}/hephae-docker/hephae-forge:latest"
info "Updating job image to latest..."
gcloud run jobs update "$JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --quiet 2>/dev/null
ok "Job updated to latest image"

# ──────────────────────────────────────────────────────────────
# Execute
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Triggering integration tests ──${NC}"
echo "   Job:     ${JOB_NAME}"
echo "   Region:  ${REGION}"
echo "   Project: ${PROJECT_ID}"
echo ""
info "Waiting for completion (this may take 5-15 minutes)..."
echo ""

gcloud run jobs execute "$JOB_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --wait

EXEC_EXIT=$?
echo ""

# ──────────────────────────────────────────────────────────────
# Fetch report URL from logs
# ──────────────────────────────────────────────────────────────
info "Fetching test report URL from logs..."
sleep 5  # allow log propagation

REPORT_URL=$(gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME} AND textPayload=~'TEST REPORT:'" \
    --project "$PROJECT_ID" \
    --limit 1 \
    --freshness 20m \
    --format "value(textPayload)" 2>/dev/null \
    | grep -oE 'https://[^ ]+' | head -1)

echo ""
if [[ -n "$REPORT_URL" ]]; then
    echo -e "${BOLD}${GREEN}══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  TEST REPORT: ${REPORT_URL}${NC}"
    echo -e "${BOLD}${GREEN}══════════════════════════════════════════════${NC}"
else
    warn "Could not find report URL in logs."
    echo "  Check GCS directly: gcloud storage ls gs://${BUCKET}/test-reports/ | sort | tail -1"
    echo "  Or view logs: gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --project ${PROJECT_ID} --limit 100 --format 'value(textPayload)'"
fi

exit $EXEC_EXIT
