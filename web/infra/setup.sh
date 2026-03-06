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
#   ./infra/setup.sh                    # Interactive — prompts for secret values
#   ./infra/setup.sh --check-only       # Just verify prerequisites, don't create anything
# ─────────────────────────────────────────────────────────────

PROJECT_ID="hephae-co-dev"
REGION="us-east1"
SERVICE_NAME="hephae-forge"
REPO="hephae-docker"
SERVICE_ACCOUNT_NAME="hephae-forge"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GCS_BUCKET="everything-hephae"
BQ_DATASET="hephae"

# Secrets that Cloud Run needs at runtime
REQUIRED_SECRETS=("GEMINI_API_KEY" "BLS_API_KEY" "FRED_API_KEY")

# GCP APIs required by the stack
REQUIRED_APIS=(
  "run.googleapis.com"                   # Cloud Run
  "cloudbuild.googleapis.com"            # Cloud Build
  "artifactregistry.googleapis.com"      # Artifact Registry
  "secretmanager.googleapis.com"         # Secret Manager
  "firestore.googleapis.com"             # Firestore
  "bigquery.googleapis.com"              # BigQuery
  "storage.googleapis.com"               # GCS
)

# IAM roles for the service account
SA_ROLES=(
  "roles/datastore.user"                 # Firestore read/write
  "roles/bigquery.dataEditor"            # BigQuery insert
  "roles/bigquery.jobUser"               # BigQuery run queries
  "roles/storage.objectAdmin"            # GCS upload/delete
  "roles/secretmanager.secretAccessor"   # Read secrets at runtime
)

# ─────────────────────────────────────────────────────────────
# Parse flags
# ─────────────────────────────────────────────────────────────
CHECK_ONLY=false
for arg in "$@"; do
  case $arg in
    --check-only) CHECK_ONLY=true ;;
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
echo "  Hephae Forge — GCP Setup"
echo "  Project: ${PROJECT_ID} | Region: ${REGION}"
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
# 3. Secret Manager secrets
# ─────────────────────────────────────────────────────────────
echo "── Secrets ───────────────────────────────────"

EXISTING_SECRETS=$(gcloud secrets list --format="value(name)" --project="$PROJECT_ID" 2>/dev/null || echo "")

for secret in "${REQUIRED_SECRETS[@]}"; do
  if echo "$EXISTING_SECRETS" | grep -q "^${secret}$"; then
    # Check if it has at least one version
    VERSION_COUNT=$(gcloud secrets versions list "$secret" --project="$PROJECT_ID" --format="value(name)" --filter="state=ENABLED" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$VERSION_COUNT" -gt 0 ]; then
      check_pass "$secret (${VERSION_COUNT} active version(s))"
    else
      check_warn "$secret exists but has no enabled versions — add one with:"
      echo "         echo -n 'your-value' | gcloud secrets versions add $secret --data-file=- --project=$PROJECT_ID"
    fi
  else
    if $CHECK_ONLY; then
      check_fail "$secret (does not exist)"
    else
      echo ""
      # GEMINI_API_KEY is required, others are optional
      if [ "$secret" = "GEMINI_API_KEY" ]; then
        echo "  ${secret} is REQUIRED. Enter the value (input hidden):"
      else
        echo "  ${secret} is optional (has fallbacks). Enter value or press Enter to skip:"
      fi
      read -rs SECRET_VALUE
      echo ""

      if [ -n "$SECRET_VALUE" ]; then
        gcloud secrets create "$secret" --project="$PROJECT_ID" --quiet
        echo -n "$SECRET_VALUE" | gcloud secrets versions add "$secret" \
          --data-file=- --project="$PROJECT_ID" --quiet
        check_pass "$secret (just created)"
        CREATED=$((CREATED + 1))
      else
        if [ "$secret" = "GEMINI_API_KEY" ]; then
          echo "  ✗ GEMINI_API_KEY is required! Create it manually:"
          echo "    echo -n 'your-key' | gcloud secrets create $secret --data-file=- --project=$PROJECT_ID"
          FAIL=$((FAIL + 1))
        else
          # Create the secret with a placeholder so Cloud Run doesn't fail on missing ref
          gcloud secrets create "$secret" --project="$PROJECT_ID" --quiet
          echo -n "placeholder" | gcloud secrets versions add "$secret" \
            --data-file=- --project="$PROJECT_ID" --quiet
          check_warn "$secret created with placeholder — update later when you have the key"
          CREATED=$((CREATED + 1))
        fi
      fi
    fi
  fi
done
echo ""

# ─────────────────────────────────────────────────────────────
# 4. Artifact Registry
# ─────────────────────────────────────────────────────────────
echo "── Artifact Registry ─────────────────────────"

if gcloud artifacts repositories describe "$REPO" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  check_pass "Repository: ${REPO}"
else
  if $CHECK_ONLY; then
    check_fail "Repository: ${REPO} (does not exist)"
  else
    gcloud artifacts repositories create "$REPO" \
      --repository-format=docker \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --description="Hephae Docker images" --quiet
    check_pass "Repository: ${REPO} (just created)"
    CREATED=$((CREATED + 1))
  fi
fi
echo ""

# ─────────────────────────────────────────────────────────────
# 5. GCS Bucket
# ─────────────────────────────────────────────────────────────
echo "── GCS Bucket ────────────────────────────────"

if gcloud storage buckets describe "gs://${GCS_BUCKET}" --project="$PROJECT_ID" &>/dev/null; then
  check_pass "Bucket: ${GCS_BUCKET}"

  # Check public access (allUsers as objectViewer)
  BUCKET_IAM=$(gcloud storage buckets get-iam-policy "gs://${GCS_BUCKET}" --format=json 2>/dev/null)
  if echo "$BUCKET_IAM" | grep -q "allUsers"; then
    check_pass "  Public read access (allUsers)"
  else
    if $CHECK_ONLY; then
      check_fail "  Public read access not configured"
    else
      gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
        --member="allUsers" --role="roles/storage.objectViewer" --quiet &>/dev/null
      check_pass "  Public read access (just configured)"
      CREATED=$((CREATED + 1))
    fi
  fi
else
  if $CHECK_ONLY; then
    check_fail "Bucket: ${GCS_BUCKET} (does not exist)"
  else
    gcloud storage buckets create "gs://${GCS_BUCKET}" \
      --project="$PROJECT_ID" --location="$REGION" --uniform-bucket-level-access --quiet
    gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
      --member="allUsers" --role="roles/storage.objectViewer" --quiet &>/dev/null
    check_pass "Bucket: ${GCS_BUCKET} (just created with public read)"
    CREATED=$((CREATED + 1))
  fi
fi
echo ""

# ─────────────────────────────────────────────────────────────
# 6. BigQuery Dataset
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

# Check required tables exist (they are auto-created by bqInsert on first write,
# but we verify here for completeness)
for table in "analyses" "discoveries" "interactions"; do
  if bq show "${PROJECT_ID}:${BQ_DATASET}.${table}" &>/dev/null; then
    check_pass "  Table: ${table}"
  else
    check_warn "  Table: ${table} — will be auto-created on first agent run"
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
  echo "  Ready to deploy:"
  echo "    ./infra/deploy.sh"
else
  echo "  ${PASS} passed, ${FAIL} failed, ${CREATED} created"
  echo ""
  echo "  Fix the failures above, then re-run:"
  echo "    ./infra/setup.sh"
fi
echo "══════════════════════════════════════════════"
echo ""
