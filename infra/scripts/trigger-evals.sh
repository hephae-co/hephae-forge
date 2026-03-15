#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# trigger-evals.sh — Run the agent-evals Cloud Run Job
#
# Usage:
#   bash infra/scripts/trigger-evals.sh                       # all agents, static evals
#   bash infra/scripts/trigger-evals.sh --agent seo_auditor   # single agent
#   bash infra/scripts/trigger-evals.sh --human-curated        # Firestore-backed evals
#   bash infra/scripts/trigger-evals.sh --unit-tests           # fast mocked unit tests (no LLM cost)
#   bash infra/scripts/trigger-evals.sh --status               # check last execution
#
# Prerequisites:
#   1. Build & push the image:  bash infra/scripts/deploy.sh
#   2. Create the job:          bash infra/scripts/deploy-eval-job.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="us-central1"
JOB_NAME="agent-evals"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ──────────────────────────────────────────────────────────────
# Parse flags
# ──────────────────────────────────────────────────────────────
STATUS_ONLY=false
AGENT=""
HUMAN_CURATED=false
UNIT_TESTS=false
NUM_RUNS=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --status)
            STATUS_ONLY=true
            shift
            ;;
        --agent)
            if [[ -z "${2:-}" ]]; then fail "--agent requires a value (e.g. seo_auditor)"; fi
            AGENT="$2"
            shift 2
            ;;
        --human-curated)
            HUMAN_CURATED=true
            shift
            ;;
        --unit-tests)
            UNIT_TESTS=true
            shift
            ;;
        --num-runs)
            if [[ -z "${2:-}" ]]; then fail "--num-runs requires a value"; fi
            NUM_RUNS="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,13p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            fail "Unknown flag: $1"
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────
# --status: show last execution info
# ──────────────────────────────────────────────────────────────
if $STATUS_ONLY; then
    echo -e "${BOLD}── Last executions (${JOB_NAME}) ──${NC}"
    gcloud run jobs executions list \
        --job "$JOB_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --limit 5 \
        --format "table(name, createTime.date('%Y-%m-%d %H:%M'), status.completionTime.date('%H:%M'), status.succeededCount, status.failedCount)"
    echo ""
    info "View logs:"
    echo "  gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' \\"
    echo "    --project ${PROJECT_ID} --limit 200 --format 'value(textPayload)'"
    exit 0
fi

# ──────────────────────────────────────────────────────────────
# Verify job exists
# ──────────────────────────────────────────────────────────────
if ! gcloud run jobs describe "$JOB_NAME" \
    --region "$REGION" --project "$PROJECT_ID" &>/dev/null; then
    fail "Job '${JOB_NAME}' not found. Run: bash infra/scripts/deploy-eval-job.sh"
fi

# ──────────────────────────────────────────────────────────────
# Update image to latest tag
# ──────────────────────────────────────────────────────────────
TAG=$(git rev-parse --short HEAD)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/hephae-forge-api:${TAG}"
info "Pinning job to image tag: ${TAG}"
gcloud run jobs update "$JOB_NAME" \
    --image "$IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --quiet 2>/dev/null
ok "Job updated."

# ──────────────────────────────────────────────────────────────
# Build override command
# ──────────────────────────────────────────────────────────────
PYTHONPATH_VAL="/app:/app/apps/api"

if $UNIT_TESTS; then
    # Unit test mode: fast, fully mocked, no LLM calls
    # Job command is already "python", so args start with -m
    EVAL_LABEL="unit tests"
    UNIT_DIRS="/app/tests/db /app/tests/workflows /app/tests/api /app/tests/agents /app/tests/integration"
    OVERRIDE_CMD="-m,pytest,${UNIT_DIRS// /,},-v,--tb=short,--noconftest"
    if [[ -n "$AGENT" ]]; then
        OVERRIDE_CMD="${OVERRIDE_CMD},-k,${AGENT}"
    fi
elif $HUMAN_CURATED; then
    # Human-curated eval mode: pytest with Firestore-backed EvalSets
    EVAL_LABEL="human-curated evals"
    OVERRIDE_CMD="-m,pytest,/app/tests/evals/test_agent_evals_human.py,-m,human_curated,-v,--tb=short"
    if [[ -n "$AGENT" ]]; then
        OVERRIDE_CMD="${OVERRIDE_CMD},-k,${AGENT}"
        EVAL_LABEL="${EVAL_LABEL} [${AGENT}]"
    fi
else
    # Static eval mode: run_all.py with file-based test cases
    EVAL_LABEL="static evals"
    if [[ -n "$AGENT" ]]; then
        OVERRIDE_CMD="/app/tests/evals/run_all.py,--agent,${AGENT},--num-runs,${NUM_RUNS}"
        EVAL_LABEL="${EVAL_LABEL} [${AGENT}]"
    else
        OVERRIDE_CMD="/app/tests/evals/run_all.py,--num-runs,${NUM_RUNS}"
    fi
fi

# ──────────────────────────────────────────────────────────────
# Execute
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Triggering agent evals ──${NC}"
echo "   Job:    ${JOB_NAME}"
echo "   Mode:   ${EVAL_LABEL}"
echo "   Image:  ${TAG}"
echo ""
warn "This runs real LLM calls — expect 5-45 minutes and Gemini API costs."
echo ""
info "Waiting for completion..."
echo ""

gcloud run jobs execute "$JOB_NAME" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --args="$OVERRIDE_CMD" \
    --update-env-vars "PYTHONPATH=${PYTHONPATH_VAL}" \
    --wait

EXEC_EXIT=$?
echo ""

# ──────────────────────────────────────────────────────────────
# Show log tail
# ──────────────────────────────────────────────────────────────
info "Fetching result summary from logs..."
sleep 5

gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}" \
    --project "$PROJECT_ID" \
    --limit 50 \
    --freshness 30m \
    --format "value(textPayload)" 2>/dev/null \
    | grep -E "(PASSED|FAILED|ERROR|passed|failed|Results:|=====)" \
    | tail -20 || true

echo ""
if [[ $EXEC_EXIT -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}All evals passed.${NC}"
else
    echo -e "${RED}${BOLD}Some evals failed (exit ${EXEC_EXIT}).${NC}"
    echo ""
    info "Full logs:"
    echo "  gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' \\"
    echo "    --project ${PROJECT_ID} --limit 500 --format 'value(textPayload)'"
fi

exit $EXEC_EXIT
