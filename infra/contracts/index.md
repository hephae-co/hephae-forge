# Hephae Forge Documentation

Internal documentation for the Hephae Forge pipeline — auto-generated from the codebase and deployed on every push to `main`.

## Quick Links

| Section | What's In It |
|---------|-------------|
| [Firestore Schema](firestore-schema.md) | Document shapes for businesses, workflows, tasks |
| [BigQuery Schema](bigquery-schema.md) | Append-only historical tables (analyses, evaluations) |
| [GCS Conventions](gcs-conventions.md) | Bucket paths for reports, menus, screenshots |
| [Web API Routes](api-web.md) | Customer-facing API endpoints |
| [Admin API Routes](api-admin.md) | Admin/workflow management endpoints |
| [Qualification Pipeline](qualification-pipeline-design.md) | 3-tier discovery architecture design |
| [Unified Pipeline](unified-pipeline-design.md) | Combined qualification + industry intelligence |
| [Evaluation Standards](eval-standards.md) | Pass thresholds, evaluator criteria |
| [Eval Ground Truth](eval-ground-truth.md) | Synthetic test cases for evaluator validation |

## Refreshing Docs

These docs are generated from the codebase using the `/hephae-refresh-docs` Claude Code skill:

```bash
# In Claude Code, run:
/hephae-refresh-docs

# Then commit and push — GitHub Actions auto-deploys
git add infra/contracts/ mkdocs.yml
git commit -m "docs: refresh contracts"
git push
```

## Architecture

```
hephae-forge/
├── apps/
│   ├── web/        → Next.js 16 customer UI
│   ├── admin/      → Next.js 14.1 admin dashboard
│   └── api/        → FastAPI unified backend
├── agents/         → All AI agents (discovery, qualification, capabilities, evaluators)
├── lib/
│   ├── common/     → Shared models, config, auth
│   ├── db/         → Firestore, BigQuery, GCS access
│   └── integrations/ → 3rd-party API clients
└── infra/
    └── contracts/  → This documentation
```
