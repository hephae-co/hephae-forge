#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Integration Test Runner for MarginSurgeon
#
# Usage:
#   ./scripts/test-integration.sh                     # all levels
#   ./scripts/test-integration.sh --level 1            # google search only
#   ./scripts/test-integration.sh --level 2            # locator agent only
#   ./scripts/test-integration.sh --level 3            # full pipeline (needs playwright)
#   ./scripts/test-integration.sh --level 4            # firestore structure
#   ./scripts/test-integration.sh --level 5            # hallucination check
#   ./scripts/test-integration.sh --level 1 --level 2  # multiple levels
#   ./scripts/test-integration.sh -k bosphorus         # single business
#   ./scripts/test-integration.sh --cloud              # cloud-safe subset (L1-L2)
#   ./scripts/test-integration.sh --report             # generate HTML + JUnit reports
#   ./scripts/test-integration.sh -v                   # verbose pytest output
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# State
LEVELS=()
PYTEST_EXTRA_ARGS=()
CLOUD_MODE=false
STARTED_CRAWL4AI=false
VERBOSE=false
REPORT_MODE=false
RUN_ID=""

# ──────────────────────────────────────────────────────────────
# Level -> test file / name lookup (Bash 3.x compatible)
# ──────────────────────────────────────────────────────────────
level_file() {
    case "$1" in
        1) echo "backend/tests/integration/test_google_search.py" ;;
        2) echo "backend/tests/integration/test_locator_agent.py" ;;
        3) echo "backend/tests/integration/test_discovery_pipeline.py" ;;
        4) echo "backend/tests/integration/test_firestore_structure.py" ;;
        5) echo "backend/tests/integration/test_hallucination_check.py" ;;
    esac
}

level_name() {
    case "$1" in
        1) echo "Google Search" ;;
        2) echo "Locator Agent" ;;
        3) echo "Discovery Pipeline" ;;
        4) echo "Firestore Structure" ;;
        5) echo "Hallucination Check" ;;
    esac
}

# Levels that require Playwright/crawl4ai
BROWSER_LEVELS="3 4 5"

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
header() { echo -e "\n${BOLD}── $* ──${NC}"; }

usage() {
    sed -n '2,17p' "$0" | sed 's/^# \?//'
    exit 0
}

# ──────────────────────────────────────────────────────────────
# Environment detection
# ──────────────────────────────────────────────────────────────
# Cloud Run Services set K_SERVICE; Cloud Run Jobs set CLOUD_RUN_JOB
IS_CLOUD_RUN_SERVICE=false
IS_CLOUD_RUN_JOB=false

if [[ -n "${K_SERVICE:-}" ]]; then
    IS_CLOUD_RUN_SERVICE=true
fi
if [[ -n "${CLOUD_RUN_JOB:-}" ]]; then
    IS_CLOUD_RUN_JOB=true
fi

IS_CLOUD_RUN=false
if $IS_CLOUD_RUN_SERVICE || $IS_CLOUD_RUN_JOB; then
    IS_CLOUD_RUN=true
fi

# ──────────────────────────────────────────────────────────────
# Argument parsing
# ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --level)
            if [[ -z "${2:-}" ]] || ! echo "$2" | grep -qE '^[1-5]$'; then
                fail "--level requires a value between 1 and 5"
            fi
            LEVELS+=("$2")
            shift 2
            ;;
        --cloud)
            CLOUD_MODE=true
            shift
            ;;
        --report)
            REPORT_MODE=true
            shift
            ;;
        --run-id)
            if [[ -z "${2:-}" ]]; then
                fail "--run-id requires a value"
            fi
            RUN_ID="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        -k)
            if [[ -z "${2:-}" ]]; then
                fail "-k requires a filter expression"
            fi
            PYTEST_EXTRA_ARGS+=("-k" "$2")
            shift 2
            ;;
        *)
            PYTEST_EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# ──────────────────────────────────────────────────────────────
# Cloud Run handling
# ──────────────────────────────────────────────────────────────

# Cloud Run Services: restrict to L1-L2 (no Playwright, not designed for testing)
if $IS_CLOUD_RUN_SERVICE; then
    CLOUD_MODE=true
    info "Detected Cloud Run Service (K_SERVICE=${K_SERVICE})"
fi

# Cloud Run Jobs: auto-enable reports, run all levels (image has Playwright)
if $IS_CLOUD_RUN_JOB; then
    REPORT_MODE=true
    info "Detected Cloud Run Job (CLOUD_RUN_JOB=${CLOUD_RUN_JOB})"
fi

if $CLOUD_MODE; then
    header "Cloud Run mode -- restricting to Levels 1-2"
    LEVELS=(1 2)
fi

# Default: all levels
if [[ ${#LEVELS[@]} -eq 0 ]]; then
    LEVELS=(1 2 3 4 5)
fi

# Generate run ID for reports
if $REPORT_MODE && [[ -z "$RUN_ID" ]]; then
    RUN_ID=$(date +%Y%m%d-%H%M%S)
fi

# ──────────────────────────────────────────────────────────────
# Resolve Python interpreter
# ──────────────────────────────────────────────────────────────
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    fail "No Python interpreter found"
fi

# ──────────────────────────────────────────────────────────────
# Preflight checks
# ──────────────────────────────────────────────────────────────
header "Preflight checks"

# 1. Load .env.local (only if it exists — Cloud Run uses Secret Manager)
if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
    while IFS='=' read -r key value; do
        case "$key" in
            ""|\#*) continue ;;
        esac
        key=$(echo "$key" | xargs)
        if [ -z "$(eval echo "\${${key}:-}")" ]; then
            export "$key"="$value"
        fi
    done < <(grep -v '^\s*#' "$PROJECT_ROOT/.env.local" | grep -v '^\s*$')
    ok "Loaded .env.local"
elif ! $IS_CLOUD_RUN; then
    warn "No .env.local found -- relying on existing environment"
fi

# 2. GEMINI_API_KEY
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    fail "GEMINI_API_KEY is not set. Add it to .env.local or export it."
fi
ok "GEMINI_API_KEY is set"

# 3. Python
PY_VERSION=$("$PYTHON" --version 2>&1)
ok "Python: $PY_VERSION ($PYTHON)"

# 4. pytest
if ! "$PYTHON" -m pytest --version &>/dev/null; then
    fail "pytest not installed -- run: .venv/bin/pip install -e '.[dev]'"
fi
ok "pytest available"

# 5. pytest-html (only if --report)
if $REPORT_MODE; then
    if ! "$PYTHON" -c "import pytest_html" 2>/dev/null; then
        info "Installing pytest-html..."
        "$PYTHON" -m pip install pytest-html --quiet 2>/dev/null || \
            "$PYTHON" -m pip install --user pytest-html --quiet
    fi
    ok "pytest-html available"
fi

# ──────────────────────────────────────────────────────────────
# Browser check (only if running Levels 3-5, not on Cloud Run)
# ──────────────────────────────────────────────────────────────
needs_browser=false
for level in "${LEVELS[@]}"; do
    for bl in $BROWSER_LEVELS; do
        if [[ "$level" == "$bl" ]]; then
            needs_browser=true
            break 2
        fi
    done
done

if $needs_browser && ! $IS_CLOUD_RUN; then
    header "Playwright browser check"

    PW_CACHE="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/Library/Caches/ms-playwright}"
    if [[ -d "$PW_CACHE" ]] && [[ -n "$(ls -A "$PW_CACHE" 2>/dev/null)" ]]; then
        BROWSER_COUNT=$(find "$PW_CACHE" -maxdepth 1 -type d \( -name "chromium-*" -o -name "firefox-*" -o -name "webkit-*" \) 2>/dev/null | wc -l | xargs)
        ok "Playwright browsers found at $PW_CACHE ($BROWSER_COUNT engines)"
    else
        warn "Playwright browsers not found at $PW_CACHE"
        echo -e "  Install with: ${BOLD}npx playwright install${NC}"
        echo -e "  Or skip browser tests: ${BOLD}./scripts/test-integration.sh --level 1 --level 2${NC}"
        fail "Playwright browsers required for Levels 3-5"
    fi
fi

# ──────────────────────────────────────────────────────────────
# crawl4ai lifecycle (optional -- pipeline degrades gracefully)
# ──────────────────────────────────────────────────────────────
if $needs_browser && ! $IS_CLOUD_RUN; then
    header "crawl4ai sidecar (optional)"

    CRAWL4AI_URL="${CRAWL4AI_URL:-http://localhost:11235}"

    if curl -sf "${CRAWL4AI_URL}/health" &>/dev/null; then
        ok "crawl4ai already running at $CRAWL4AI_URL"
        export CRAWL4AI_URL
    elif command -v docker &>/dev/null; then
        info "Starting crawl4ai container..."
        if docker run -d \
            --name crawl4ai-integ-test \
            -p 11235:11235 \
            --pull missing \
            unclecode/crawl4ai:latest &>/dev/null; then
            STARTED_CRAWL4AI=true
            export CRAWL4AI_URL="http://localhost:11235"

            info "Waiting for crawl4ai to become healthy..."
            for i in $(seq 1 30); do
                if curl -sf "${CRAWL4AI_URL}/health" &>/dev/null; then
                    ok "crawl4ai ready (took ${i}s)"
                    break
                fi
                if [[ $i -eq 30 ]]; then
                    warn "crawl4ai failed to start -- continuing without it"
                    STARTED_CRAWL4AI=false
                    docker rm -f crawl4ai-integ-test &>/dev/null || true
                fi
                sleep 1
            done
        else
            warn "Failed to start crawl4ai container -- continuing without it"
        fi
    else
        warn "Docker not available -- skipping crawl4ai (pipeline degrades gracefully)"
    fi
fi

# ──────────────────────────────────────────────────────────────
# Cleanup trap
# ──────────────────────────────────────────────────────────────
cleanup() {
    if $STARTED_CRAWL4AI; then
        echo ""
        info "Stopping crawl4ai container..."
        docker rm -f crawl4ai-integ-test &>/dev/null && ok "crawl4ai stopped" || true
    fi
}
trap cleanup EXIT

# ──────────────────────────────────────────────────────────────
# Build test file list
# ──────────────────────────────────────────────────────────────
header "Test plan"

TEST_FILES=()
for level in "${LEVELS[@]}"; do
    file="$(level_file "$level")"
    name="$(level_name "$level")"
    if [[ -f "$PROJECT_ROOT/$file" ]]; then
        TEST_FILES+=("$file")
        info "Level $level: $name ($file)"
    else
        warn "Level $level: test file not found -- $file (skipping)"
    fi
done

if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
    fail "No test files to run"
fi

# ──────────────────────────────────────────────────────────────
# Report setup
# ──────────────────────────────────────────────────────────────
REPORT_DIR=""
if $REPORT_MODE; then
    if $IS_CLOUD_RUN; then
        REPORT_DIR="/tmp/test-reports/${RUN_ID}"
    else
        REPORT_DIR="${PROJECT_ROOT}/test-reports/${RUN_ID}"
    fi
    mkdir -p "$REPORT_DIR"
    info "Report output: $REPORT_DIR"
fi

# ──────────────────────────────────────────────────────────────
# Run pytest
# ──────────────────────────────────────────────────────────────
header "Running integration tests"

PYTEST_ARGS=(
    "-m" "integration"
    "--timeout=300"
    "--tb=short"
)

if $VERBOSE; then
    PYTEST_ARGS+=("-v" "-s")
else
    PYTEST_ARGS+=("-v")
fi

# Report outputs
if $REPORT_MODE; then
    PYTEST_ARGS+=(
        "--html=${REPORT_DIR}/report.html"
        "--self-contained-html"
        "--junitxml=${REPORT_DIR}/junit.xml"
    )
fi

# Extra args (like -k filters)
if [[ ${#PYTEST_EXTRA_ARGS[@]} -gt 0 ]]; then
    PYTEST_ARGS+=("${PYTEST_EXTRA_ARGS[@]}")
fi

# Test files
PYTEST_ARGS+=("${TEST_FILES[@]}")

echo -e "${CYAN}$PYTHON -m pytest ${PYTEST_ARGS[*]}${NC}\n"

cd "$PROJECT_ROOT"

set +e
"$PYTHON" -m pytest "${PYTEST_ARGS[@]}"
EXIT_CODE=$?
set -e

# ──────────────────────────────────────────────────────────────
# Upload report to GCS (Cloud Run only)
# ──────────────────────────────────────────────────────────────
if $REPORT_MODE && [[ -f "${REPORT_DIR}/report.html" ]]; then
    if $IS_CLOUD_RUN; then
        header "Uploading test report to GCS"
        "$PYTHON" "${PROJECT_ROOT}/scripts/upload_test_report.py" "$REPORT_DIR" "$RUN_ID"
    else
        echo ""
        REPORT_PATH="${REPORT_DIR}/report.html"
        echo -e "${BOLD}TEST REPORT: file://${REPORT_PATH}${NC}"
        if [[ -f "${REPORT_DIR}/junit.xml" ]]; then
            echo -e "JUnit XML:   file://${REPORT_DIR}/junit.xml"
        fi
    fi
fi

# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}All integration tests passed${NC}"
else
    echo -e "${RED}${BOLD}Some integration tests failed (exit code $EXIT_CODE)${NC}"
fi

exit $EXIT_CODE
