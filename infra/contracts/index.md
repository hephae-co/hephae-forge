# Hephae Forge Documentation

> Internal documentation for the Hephae Forge pipeline.
> Last refreshed: 2026-03-15. Run `/hephae-refresh-docs` in Claude Code to regenerate from codebase.

## Architecture

| Doc | Description |
|-----|-------------|
| [System Overview](architecture/overview.md) | Service topology, package dependencies, model tiers, auth, database rules |
| [Infrastructure & Deployment](architecture/infrastructure.md) | GCP topology, env vars, Cloud Run config, deploy scripts, bootstrap |
| [Workflow Pipeline](architecture/workflow-pipeline.md) | Phase transitions, capability registry, qualification scoring, threshold formula |

## Database

| Doc | Description |
|-----|-------------|
| [Firestore Schema](firestore-schema.md) | All collections — businesses, workflows, tasks, research, fixtures |
| [BigQuery Schema](bigquery-schema.md) | Append-only tables — analyses, discoveries, interactions |
| [GCS Conventions](gcs-conventions.md) | Bucket paths for reports, menus, social cards |

## API

| Doc | Description |
|-----|-------------|
| [Web Routes](api-web.md) | Customer-facing endpoints — discover, analyze, chat, social |
| [Admin Routes](api-admin.md) | Workflow CRUD, research, tasks, testing, content, stats |

## Agents

| Doc | Description |
|-----|-------------|
| [Agent Catalog](agents/agent-catalog.md) | All 48 agents — versions, models, tools, architecture |
| [Prompt Catalog](agents/prompt-catalog.md) | Full instruction text for every LlmAgent in the system |

## Pipeline Design

| Doc | Description |
|-----|-------------|
| [Qualification Design](qualification-pipeline-design.md) | 3-tier architecture: research, scan, qualification |
| [Unified Pipeline Design](unified-pipeline-design.md) | Combined qualification + industry intelligence |
| [Evaluation Standards](eval-standards.md) | Pass thresholds, evaluator criteria, hallucination rules |
| [Eval Ground Truth](eval-ground-truth.md) | Test fixtures and ground truth for evaluator validation |

## Other

| Doc | Description |
|-----|-------------|
| [Changelog](changelog.md) | Breaking changes and version history |

---

## System at a Glance

```
┌──────────────┐     ┌──────────────┐
│  apps/web/   │     │ apps/admin/  │
│  Next.js 16  │     │ Next.js 14.1 │
└──────┬───────┘     └──────┬───────┘
       └──────────┬─────────┘
                  ▼
       ┌──────────────────┐
       │   apps/api/      │
       │   FastAPI         │──→ 48 AI Agents (Gemini)
       │   Unified API    │──→ Firestore / BigQuery / GCS
       └──────────────────┘

Workflow: DISCOVERY → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH
Agents:   16 discovery │ 12 capability │ 11 social/marketing │ 4 evaluators │ 1 insights
Model:    gemini-3.1-flash-lite-preview (fallback: gemini-3-flash-preview)
```

## Refreshing These Docs

```bash
# In Claude Code:
/hephae-refresh-docs            # regenerate all docs from code
/hephae-refresh-docs db api     # just database + API docs
/hephae-refresh-docs agents     # just agent + prompt catalogs

# Then commit and push — GitHub Actions auto-deploys
git add infra/contracts/ && git commit -m "docs: refresh" && git push
```
