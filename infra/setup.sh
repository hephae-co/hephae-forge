#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# setup.sh — One-time GCP infrastructure setup for Hephae Forge
#
# Idempotent: safe to run multiple times. Skips resources that
# already exist. Use this to bootstrap a fresh project or to
# verify that all prerequisites are in place.
#
# Usage:
#   bash infra/setup.sh                    # Interactive — prompts for secret values
#   bash infra/setup.sh --check-only       # Just verify prerequisites, don't create anything
# ─────────────────────────────────────────────────────────────

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="hephae-forge"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Artifact Registry — used by all deploy scripts
AR_REPO="cloud-run-source-deploy"

# Storage buckets
GCS_BUCKET="${GCS_BUCKET:-everything-hephae}"
GCS_CDN_BUCKET="${GCS_CDN_BUCKET:-${PROJECT_ID}-prod-cdn-assets}"

# BigQuery
BQ_DATASET="hephae"

# All secrets referenced by any deploy script across the monorepo.
# Priority: REQUIRED = deploy will fail without it, OPTIONAL = has fallback or used by subset of features.
REQUIRED_SECRETS=("GEMINI_API_KEY")
OPTIONAL_SECRETS=(
  "BLS_API_KEY"
  "FRED_API_KEY"
  "GOOGLE_MAPS_API_KEY"
  "FORGE_API_SECRET"
  "FORGE_V1_API_KEY"
  "CRON_SECRET"
  "RESEND_API_KEY"
  "ADMIN_EMAIL_ALLOWLIST"
  "FIREBASE_API_KEY"
)
ALL_SECRETS=("${REQUIRED_SECRETS[@]}" "${OPTIONAL_SECRETS[@]}")

# GCP APIs required by the stack
REQUIRED_APIS=(
  "run.googleapis.com"                   # Cloud Run
  "cloudbuild.googleapis.com"            # Cloud Build
  "artifactregistry.googleapis.com"      # Artifact Registry
  "secretmanager.googleapis.com"         # Secret Manager
  "firestore.googleapis.com"             # Firestore
  "bigquery.googleapis.com"              # BigQuery
  "storage.googleapis.com"               # GCS
  "cloudscheduler.googleapis.com"        # Cloud Scheduler (heartbeat cron, discovery batch)
  "cloudtasks.googleapis.com"            # Cloud Tasks (async agent work)
)

# IAM roles for the service account
SA_ROLES=(
  "roles/datastore.user"                 # Firestore read/write
  "roles/bigquery.dataEditor"            # BigQuery insert
  "roles/bigquery.jobUser"               # BigQuery run queries
  "roles/storage.objectAdmin"            # GCS upload/delete
  "roles/secretmanager.secretAccessor"   # Read secrets at runtime
  "roles/run.invoker"                    # Invoke Cloud Run services/jobs
)

# ─────────────────────────────────────────────────────────────
# Parse flags
# ─────────────────────────────────────────────────────────────
CHECK_ONLY=false
for arg in "$@"; do
  case $arg in
    --check-only) CHECK_ONLY=true ;;
    -h|--help)
      echo "Usage: bash infra/setup.sh [--check-only]"
      echo ""
      echo "  --check-only   Verify prerequisites without creating anything"
      exit 0
      ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
PASS=0
FAIL=0
CREATED=0

check_pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
check_fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }
check_warn() { echo "  ⚠ $1"; }

# ─────────────────────────────────────────────────────────────
# 0. Pre-flight: gcloud installed and authenticated
# ─────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  Hephae Forge — GCP Infrastructure Setup"
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "══════════════════════════════════════════════"
echo ""

if ! command -v gcloud &>/dev/null; then
  echo "✗ gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# Ensure correct project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
  if $CHECK_ONLY; then
    check_fail "gcloud project is '${CURRENT_PROJECT}', expected '${PROJECT_ID}'"
  else
    echo "  Switching gcloud project to ${PROJECT_ID}..."
    gcloud config set project "$PROJECT_ID" --quiet
  fi
fi

ACCOUNT=$(gcloud config get-value account 2>/dev/null)
if [ -z "$ACCOUNT" ]; then
  echo "✗ Not authenticated. Run: gcloud auth login"
  exit 1
fi
echo "  Authenticated as: ${ACCOUNT}"
echo ""

# ─────────────────────────────────────────────────────────────
# 1. Enable required APIs
# ─────────────────────────────────────────────────────────────
echo "── APIs ──────────────────────────────────────"

ENABLED_APIS=$(gcloud services list --enabled --format="value(config.name)" --project="$PROJECT_ID" 2>/dev/null)

for api in "${REQUIRED_APIS[@]}"; do
  if echo "$ENABLED_APIS" | grep -q "^${api}$"; then
    check_pass "$api"
  else
    if $CHECK_ONLY; then
      check_fail "$api (not enabled)"
    else
      echo "  Enabling ${api}..."
      gcloud services enable "$api" --project="$PROJECT_ID" --quiet
      check_pass "$api (just enabled)"
      CREATED=$((CREATED + 1))
    fi
  fi
done
echo ""

# ─────────────────────────────────────────────────────────────
# 2. Service Account
# ─────────────────────────────────────────────────────────────
echo "── Service Account ───────────────────────────"

if gcloud iam service-accounts describe "$SERVICE_ACCOUNT" --project="$PROJECT_ID" &>/dev/null; then
  check_pass "Service account: ${SERVICE_ACCOUNT}"
else
  if $CHECK_ONLY; then
    check_fail "Service account: ${SERVICE_ACCOUNT} (does not exist)"
  else
    echo "  Creating service account..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
      --display-name="Hephae Forge Cloud Run" \
      --project="$PROJECT_ID" --quiet
    check_pass "Service account: ${SERVICE_ACCOUNT} (just created)"
    CREATED=$((CREATED + 1))
  fi
fi

# IAM role bindings
CURRENT_POLICY=$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json 2>/dev/null)

for role in "${SA_ROLES[@]}"; do
  if echo "$CURRENT_POLICY" | grep -q "\"$role\"" && \
     echo "$CURRENT_POLICY" | grep -q "$SERVICE_ACCOUNT"; then
    check_pass "  $role"
  else
    if $CHECK_ONLY; then
      check_fail "  $role (not bound)"
    else
      gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="$role" --quiet &>/dev/null
      check_pass "  $role (just bound)"
      CREATED=$((CREATED + 1))
    fi
  fi
done
echo ""

# ─────────────────────────────────────────────────────────────
# 3. Artifact Registry
# ─────────────────────────────────────────────────────────────
echo "── Artifact Registry ─────────────────────────"

if gcloud artifacts repositories describe "$AR_REPO" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  check_pass "Repository: ${AR_REPO} (${REGION})"
else
  if $CHECK_ONLY; then
    check_fail "Repository: ${AR_REPO} (does not exist in ${REGION})"
  else
    gcloud artifacts repositories create "$AR_REPO" \
      --repository-format=docker \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --description="Hephae Docker images" --quiet
    check_pass "Repository: ${AR_REPO} (just created in ${REGION})"
    CREATED=$((CREATED + 1))
  fi
fi
echo ""

# ─────────────────────────────────────────────────────────────
# 4. Secret Manager secrets
# ─────────────────────────────────────────────────────────────
echo "── Secrets ───────────────────────────────────"

EXISTING_SECRETS=$(gcloud secrets list --format="value(name)" --project="$PROJECT_ID" 2>/dev/null || echo "")

_ensure_secret() {
  local secret="$1"
  local required="$2"  # "true" or "false"

  if echo "$EXISTING_SECRETS" | grep -q "^${secret}$"; then
    VERSION_COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" \
      --format="value(name)" --filter="state=ENABLED" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$VERSION_COUNT" -gt 0 ]; then
      check_pass "$secret (${VERSION_COUNT} active version(s))"
    else
      check_warn "$secret exists but has no enabled versions"
      echo "         echo -n 'your-value' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
    fi
  else
    if $CHECK_ONLY; then
      if [ "$required" = "true" ]; then
        check_fail "$secret (REQUIRED — does not exist)"
      else
        check_warn "$secret (optional — does not exist)"
      fi
    else
      if [ "$required" = "true" ]; then
        echo ""
        echo "  ${secret} is REQUIRED. Enter the value (input hidden):"
        read -rs SECRET_VALUE
        echo ""

        if [ -n "$SECRET_VALUE" ]; then
          gcloud secrets create "$secret" --project="$PROJECT_ID" --quiet
          echo -n "$SECRET_VALUE" | gcloud secrets versions add "$secret" \
            --data-file=- --project="$PROJECT_ID" --quiet
          check_pass "$secret (just created)"
          CREATED=$((CREATED + 1))
        else
          echo "  ✗ ${secret} is required! Create it manually:"
          echo "    echo -n 'your-key' | gcloud secrets create $secret --data-file=- --project=$PROJECT_ID"
          FAIL=$((FAIL + 1))
        fi
      else
        # Optional: create with placeholder so Cloud Run secret refs don't fail
        gcloud secrets create "$secret" --project="$PROJECT_ID" --quiet
        echo -n "placeholder" | gcloud secrets versions add "$secret" \
          --data-file=- --project="$PROJECT_ID" --quiet
        check_warn "$secret (created with placeholder — update when ready)"
        CREATED=$((CREATED + 1))
      fi
    fi
  fi
}

for secret in "${REQUIRED_SECRETS[@]}"; do
  _ensure_secret "$secret" "true"
done

for secret in "${OPTIONAL_SECRETS[@]}"; do
  _ensure_secret "$secret" "false"
done
echo ""

# ─────────────────────────────────────────────────────────────
# 5. GCS Buckets
# ─────────────────────────────────────────────────────────────
echo "── GCS Buckets ───────────────────────────────"

_ensure_bucket() {
  local bucket="$1"
  local public="${2:-false}"  # "true" for public read access

  if gcloud storage buckets describe "gs://${bucket}" --project="$PROJECT_ID" &>/dev/null; then
    check_pass "Bucket: ${bucket}"

    if [ "$public" = "true" ]; then
      BUCKET_IAM=$(gcloud storage buckets get-iam-policy "gs://${bucket}" --format=json 2>/dev/null)
      if echo "$BUCKET_IAM" | grep -q "allUsers"; then
        check_pass "  Public read access (allUsers)"
      else
        if $CHECK_ONLY; then
          check_fail "  Public read access not configured"
        else
          gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
            --member="allUsers" --role="roles/storage.objectViewer" --quiet &>/dev/null
          check_pass "  Public read access (just configured)"
          CREATED=$((CREATED + 1))
        fi
      fi
    fi
  else
    if $CHECK_ONLY; then
      check_fail "Bucket: ${bucket} (does not exist)"
    else
      gcloud storage buckets create "gs://${bucket}" \
        --project="$PROJECT_ID" --location="$REGION" --uniform-bucket-level-access --quiet
      if [ "$public" = "true" ]; then
        gcloud storage buckets add-iam-policy-binding "gs://${bucket}" \
          --member="allUsers" --role="roles/storage.objectViewer" --quiet &>/dev/null
      fi
      check_pass "Bucket: ${bucket} (just created)"
      CREATED=$((CREATED + 1))
    fi
  fi
}

# Legacy bucket (menu screenshots, menu HTML)
_ensure_bucket "$GCS_BUCKET" "true"

# CDN bucket (reports, social cards)
_ensure_bucket "$GCS_CDN_BUCKET" "true"
echo ""

# ─────────────────────────────────────────────────────────────
# 6. Firestore
# ─────────────────────────────────────────────────────────────
echo "── Firestore ─────────────────────────────────"

# Check if Firestore database exists (default database)
if gcloud firestore databases describe --project="$PROJECT_ID" &>/dev/null; then
  check_pass "Firestore database (default)"
else
  if $CHECK_ONLY; then
    check_fail "Firestore database not initialized"
  else
    echo "  Creating Firestore database (Native mode)..."
    gcloud firestore databases create \
      --project="$PROJECT_ID" \
      --location="$REGION" \
      --type=firestore-native --quiet 2>/dev/null || \
      check_warn "Firestore already exists or requires manual setup via console"
    check_pass "Firestore database (just created)"
    CREATED=$((CREATED + 1))
  fi
fi
echo ""

# ─────────────────────────────────────────────────────────────
# 7. BigQuery Dataset
# ─────────────────────────────────────────────────────────────
echo "── BigQuery ──────────────────────────────────"

if bq show "${PROJECT_ID}:${BQ_DATASET}" &>/dev/null; then
  check_pass "Dataset: ${BQ_DATASET}"
else
  if $CHECK_ONLY; then
    check_fail "Dataset: ${BQ_DATASET} (does not exist)"
  else
    bq mk --dataset --location=US "${PROJECT_ID}:${BQ_DATASET}"
    check_pass "Dataset: ${BQ_DATASET} (just created)"
    CREATED=$((CREATED + 1))
  fi
fi

# Check required tables (auto-created on first write, but verify for completeness)
for table in "analyses" "discoveries" "interactions"; do
  if bq show "${PROJECT_ID}:${BQ_DATASET}.${table}" &>/dev/null; then
    check_pass "  Table: ${table}"
  else
    check_warn "  Table: ${table} — will be auto-created on first write"
  fi
done
echo ""

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
echo "══════════════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
  echo "  ✓ All prerequisites met! (${PASS} checks passed, ${CREATED} resources created)"
  echo ""
  echo "  Deploy services:"
  echo "    bash apps/api/infra/deploy.sh      # Unified API"
  echo "    bash apps/web/infra/deploy.sh      # Web frontend"
  echo "    bash apps/admin/infra/deploy.sh    # Admin frontend"
else
  echo "  ${PASS} passed, ${FAIL} failed, ${CREATED} created"
  echo ""
  echo "  Fix the failures above, then re-run:"
  echo "    bash infra/setup.sh"
fi
echo "══════════════════════════════════════════════"
echo ""
