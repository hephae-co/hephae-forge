# Shared Python code for hephae-forge monorepo
# This package is installed as a local path dependency by both web/ and admin/.
#
# Usage in each app's pyproject.toml:
#   dependencies = ["hephae-common @ file:///../packages/common-python"]
#
# Modules to extract here (TODO):
#   - firebase.py    (Firebase Admin SDK init)
#   - auth.py        (HMAC verification, GCP identity tokens)
#   - models.py      (Shared Pydantic models: EnrichedProfile, BaseIdentity, etc.)
#   - model_config.py (Model tiers, fallback maps, agent versions)
#   - gcs.py         (GCS upload helpers, slug generation)
#   - bigquery.py    (BQ insert helpers)
