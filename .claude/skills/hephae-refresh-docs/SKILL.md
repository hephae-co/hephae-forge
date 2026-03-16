---
name: hephae-refresh-docs
description: Refresh all Hephae documentation (database schema, API routes, agent design, prompts, workflow capabilities, GCS conventions, eval standards) by reading the current codebase and updating infra/contracts/*.md files.
---

# Refresh Docs — Codebase-Driven Documentation Generator

You are a documentation generator for the Hephae pipeline. Your job is to read the **current codebase** and regenerate the contract documentation at `infra/contracts/` so it stays in sync with the code.

**Core principle:** The code is the source of truth. Read it, extract the facts, and write them into the docs. Do NOT invent information or copy stale doc content — derive everything from actual code.

## Output Location

All generated docs go to `infra/contracts/`. The directory structure is:

```
infra/contracts/
├── index.md                          # Landing page with quick links
├── architecture/
│   ├── overview.md                   # Service topology, dependencies, model tiers
│   ├── infrastructure.md             # GCP topology, env vars, deploy, Cloud Run config
│   └── workflow-pipeline.md          # Phase transitions, capabilities, scoring, threshold
├── firestore-schema.md               # All Firestore collections
├── bigquery-schema.md                # BigQuery tables
├── gcs-conventions.md                # GCS bucket paths
├── api-web.md                        # Web API endpoints
├── api-admin.md                      # Admin API endpoints
├── agents/
│   ├── agent-catalog.md              # All agents, versions, models, tools
│   └── prompt-catalog.md             # Full instruction text for every LlmAgent
├── eval-standards.md                 # Evaluator criteria, pass thresholds
├── qualification-pipeline-design.md  # PRESERVED (human-written design doc)
├── unified-pipeline-design.md        # PRESERVED (human-written design doc)
├── eval-ground-truth.md              # PRESERVED (manual test data)
└── changelog.md                      # PRESERVED (manual version history)
```

Every auto-generated doc starts with:
```
> Auto-generated from codebase on {YYYY-MM-DD}. Do not edit manually — run `/hephae-refresh-docs` to update.
```

Overwrite existing files with freshly generated content.

## Arguments

The user can optionally specify which docs to refresh:
- No args → refresh ALL docs
- `db` or `database` → just database docs (firestore-schema.md, bigquery-schema.md)
- `api` → just API docs (api-web.md, api-admin.md)
- `agents` → just agent docs (agent-catalog.md)
- `prompts` → just prompt docs (prompt-catalog.md)
- `workflow` → just workflow docs (workflow-pipeline.md)
- `eval` → just eval docs (eval-standards.md)
- `gcs` → just GCS docs (gcs-conventions.md)
- Multiple args separated by spaces (e.g., `db api agents`)

---

## PHASE 1: READ — Gather Source Data

Read the relevant source files for each doc category. Launch multiple Explore agents in parallel for independent categories.

### 1a. Database Schema Sources
```
lib/db/hephae_db/firestore/         → All Firestore collection access (read/write patterns, field names)
lib/db/hephae_db/bigquery/          → BigQuery table definitions, INSERT schemas
apps/api/hephae_api/types.py        → Pydantic models defining document shapes
lib/common/hephae_common/           → Shared models, enums
```

**Extract from Firestore code:**
- Every `collection("X").document(Y)` call → collection name, document ID pattern
- Every `.update({...})` or `.set({...})` → field names and types
- Every `.get()` with field access → which fields are read
- The PROMOTE_KEYS lists (in analysis.py, tasks.py) → which fields get promoted to top-level

**Extract from BigQuery code:**
- Table names from INSERT/SELECT queries
- Column definitions from schema declarations or INSERT column lists
- Which data flows to BigQuery vs stays in Firestore

**Extract from Pydantic models:**
- Model class names and their fields with types
- Which models map to which Firestore collections

### 1b. API Endpoint Sources
```
apps/api/hephae_api/routers/web/    → Web-facing routes
apps/api/hephae_api/routers/admin/  → Admin-facing routes
apps/api/hephae_api/routers/v1/     → Legacy v1 routes
apps/api/hephae_api/routers/batch/  → Cron/Cloud Task routes
apps/api/hephae_api/main.py         → Route registration, middleware
apps/api/hephae_api/lib/auth.py     → Auth middleware
```

**Extract from route files:**
- HTTP method + path (from decorators: `@router.get("/path")`, `@router.post("/path")`)
- Request/response models (from type annotations)
- Auth requirements (dependency injection of auth functions)
- Brief description (from docstrings or function names)
- Which router prefix they're mounted under (check main.py for `app.include_router`)

### 1c. Agent Design Sources
```
agents/hephae_agents/               → All agent directories
agents/hephae_agents/*/runner.py    → Runner entry points (stateless: identity → report)
agents/hephae_agents/*/agent.py     → Agent definitions (LlmAgent, tools, sub-agents)
apps/api/hephae_api/config.py       → AgentVersions
lib/common/hephae_common/model_config.py → Model tiers (PRIMARY, FALLBACK, etc.)
lib/common/hephae_common/model_fallback.py → Fallback logic
```

**Extract from agent code:**
- Agent name and version (from AgentVersions in config.py)
- Model tier used (from `model=AgentModels.XXX`)
- Thinking mode (from `thinking_config` or thinking parameter)
- Tools list (from `tools=[...]` in agent definition)
- Sub-agents (from `sub_agents=[...]`)
- Input/output contract (from runner function signature and return type)

### 1d. Prompt Design Sources
```
agents/hephae_agents/*/agent.py     → instruction= strings in LlmAgent definitions
agents/hephae_agents/evaluators/    → Evaluator prompts
apps/api/hephae_api/workflows/agents/ → Workflow-specific agent prompts
```

**Extract from agent definitions:**
- The `instruction=` parameter of each LlmAgent — this IS the prompt
- For multi-agent pipelines, the orchestrator prompt + each sub-agent prompt
- Evaluation prompts (what criteria each evaluator checks)
- Any dynamic prompt construction (f-strings, templates)

### 1e. Workflow & Capability Sources
```
apps/api/hephae_api/workflows/engine.py           → Phase state machine
apps/api/hephae_api/workflows/phases/              → Phase implementations
apps/api/hephae_api/workflows/capabilities/registry.py → Capability registry
apps/api/hephae_api/workflows/capabilities/display.py  → Display names
agents/hephae_agents/qualification/scanner.py      → Qualification scoring weights
agents/hephae_agents/qualification/threshold.py    → Dynamic threshold formula
```

**Extract from workflow code:**
- Phase transitions (the state machine in engine.py)
- Capability definitions (name, display_name, should_run condition, runner, evaluator)
- Qualification scoring weights (all the +N bonuses from scanner.py)
- Dynamic threshold formula (from threshold.py)
- Analysis orchestrator flow (enrichment → capabilities → insights)

### 1f. Evaluation Standards Sources
```
agents/hephae_agents/evaluators/         → All evaluator agents
apps/api/hephae_api/workflows/phases/evaluation.py → Eval orchestration
infra/contracts/eval-ground-truth.md     → Keep as-is (manual test data)
```

**Extract:**
- Pass threshold (score >= X AND !isHallucinated)
- Each evaluator's criteria (from instruction prompts)
- Evaluator model tier and thinking mode
- How evaluation results are stored

### 1g. GCS Convention Sources
```
lib/db/hephae_db/gcs/               → GCS upload/download functions
apps/api/hephae_api/                 → Any code constructing GCS paths
lib/common/hephae_common/            → CDN base URL config
```

**Extract:**
- Bucket names (from env vars or constants)
- Path patterns (from string construction in upload functions)
- What goes where (reports → CDN, menus → legacy, etc.)

---

## PHASE 2: GENERATE — Write Each Doc

Generate each document from the extracted data. Use the formats below. Each doc should:
- Start with a header and "Auto-generated" notice with timestamp
- Be structured for quick scanning (tables, code blocks, bullet lists)
- Include file references so readers can find the source code
- NOT include speculative or aspirational content — only what the code actually does

### Doc 1: `firestore-schema.md`

```markdown
# Firestore Schema
> Auto-generated from codebase on {YYYY-MM-DD}. Source of truth: `lib/db/hephae_db/firestore/` + `apps/api/hephae_api/types.py`

## Collection: `businesses`
Document ID: `{slug}` (kebab-case business name)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| officialUrl | string | enrichment | Business website URL |
| ... | ... | ... | ... |

## Collection: `workflows`
...

## Collection: `tasks`
...
```

For each collection: document ID pattern, all fields with types, which code writes them, which code reads them.

### Doc 2: `bigquery-schema.md`

```markdown
# BigQuery Schema
> Auto-generated from codebase on {YYYY-MM-DD}. Source: `lib/db/hephae_db/bigquery/`

## Dataset: `hephae`

### Table: `analyses`
| Column | Type | Description |
...
```

### Doc 3: `api-web.md`

```markdown
# Web API Routes
> Auto-generated from codebase on {YYYY-MM-DD}. Source: `apps/api/hephae_api/routers/web/`

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/businesses/{slug} | HMAC | Get business by slug |
| ... | ... | ... | ... |

### GET /api/businesses/{slug}
**Request:** ...
**Response:** ...
**Source:** `routers/web/businesses.py:42`
```

### Doc 4: `api-admin.md`

Same format as api-web.md but for admin routes.

### Doc 5: `agent-catalog.md` (NEW)

```markdown
# Agent Catalog
> Auto-generated from codebase on {YYYY-MM-DD}. Source: `agents/hephae_agents/` + `apps/api/hephae_api/config.py`

## Agent Versions
| Agent | Version | Model Tier | Thinking | Tools |
|-------|---------|------------|----------|-------|

## Discovery Agents

### Phase 1: Zipcode Scanner
- **File:** `agents/hephae_agents/discovery/runner.py`
- **Model:** {tier}
- **Input:** identity dict (name, address, officialUrl)
- **Output:** enriched_profile dict
- **Sub-agents:** {list from agent.py}

### Phase 2: Profile Enrichment
...

## Qualification Agents
...

## Capability Agents (Analysis)
### SEO Auditor
### Traffic Forecaster
### Competitive Analyzer
### Margin Surgeon
### Social Media Auditor

## Evaluator Agents
...

## Workflow Agents (Research, etc.)
...
```

### Doc 6: `prompt-catalog.md` (NEW)

```markdown
# Prompt Catalog
> Auto-generated from codebase on {YYYY-MM-DD}. Source: `agents/hephae_agents/*/agent.py`

For each agent, the full `instruction=` text is captured below. These are the actual prompts
sent to the model — edit the source file to change them.

## Discovery Phase 1: Scanner
**File:** `agents/hephae_agents/discovery/agent.py:{line}`
**Model:** {model}
```
{full instruction text}
```

## Discovery Phase 2: Contact Agent
...
```

Capture the FULL instruction text for every LlmAgent. Group by pipeline phase. Include the source file and line number.

### Doc 7: `workflow-pipeline.md` (NEW — replaces/supplements unified-pipeline-design.md with code-derived facts)

```markdown
# Workflow Pipeline Reference
> Auto-generated from codebase on {YYYY-MM-DD}

## Phase Transitions
```
DISCOVERY → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH → COMPLETED
```

## Phase: DISCOVERY
- **File:** `apps/api/hephae_api/workflows/phases/discovery.py`
- **What it does:** {derived from code}
- **Timeout:** {if any}

## Phase: QUALIFICATION
- **Scoring Weights:**
  | Signal | Points |
  |--------|--------|
  | Custom domain | +15 |
  | ... | ... |
- **Dynamic Threshold Formula:** {from threshold.py}
- **Full Probe:** {when triggered, what it does}

## Phase: ANALYSIS
- **Enrichment:** {what enrich_business_profile does}
- **Capability Registry:**
  | Capability | should_run | Runner | Evaluator |
  |------------|-----------|--------|-----------|
  | seo | officialUrl exists | ... | ... |
  | ... | ... | ... | ... |

## Phase: EVALUATION
...

## Phase: APPROVAL
...

## Phase: OUTREACH
...
```

### Doc 8: `eval-standards.md`

```markdown
# Evaluation Standards
> Auto-generated from codebase on {YYYY-MM-DD}

## Pass Threshold
score >= {N} AND isHallucinated == false

## Evaluator Configuration
| Capability | Evaluator Agent | Model Tier | Thinking Mode |
|------------|----------------|------------|---------------|

## Per-Capability Evaluation Criteria
### SEO Evaluator
{criteria from evaluator instruction prompt}

### Traffic Evaluator
{criteria from evaluator instruction prompt}
...
```

### Doc 9: `gcs-conventions.md`

```markdown
# GCS Conventions
> Auto-generated from codebase on {YYYY-MM-DD}

## Buckets
| Bucket | Env Var | Purpose |
|--------|---------|---------|

## Path Patterns
| Pattern | Example | Used By |
|---------|---------|---------|
```

---

## PHASE 3: PRESERVE — Don't Overwrite Design Docs

These files contain human-written design rationale and should NOT be overwritten:
- `infra/contracts/qualification-pipeline-design.md` — architectural design doc
- `infra/contracts/unified-pipeline-design.md` — architectural design doc
- `infra/contracts/TODO-architecture.md` — open design questions
- `infra/contracts/eval-ground-truth.md` — manual test data
- `infra/contracts/changelog.md` — manual version history

If the user asks to refresh "all", skip these files and note that they were preserved.

---

## PHASE 4: VALIDATE — Cross-Check

After generating, do a quick cross-check:
1. Every Firestore collection referenced in code should appear in firestore-schema.md
2. Every API route registered in main.py should appear in api-web.md or api-admin.md
3. Every agent in AgentVersions should appear in agent-catalog.md
4. Every capability in the registry should appear in workflow-pipeline.md
5. Every evaluator should appear in eval-standards.md

Report any gaps found during validation.

---

## PHASE 5: SUMMARY

Output a summary to the conversation:
```
Docs refreshed:
- firestore-schema.md: {N} collections, {M} fields
- bigquery-schema.md: {N} tables
- api-web.md: {N} endpoints
- api-admin.md: {N} endpoints
- agent-catalog.md: {N} agents
- prompt-catalog.md: {N} prompts captured
- workflow-pipeline.md: {N} phases, {M} capabilities
- eval-standards.md: {N} evaluators
- gcs-conventions.md: {N} path patterns

Preserved (not overwritten):
- qualification-pipeline-design.md
- unified-pipeline-design.md
- TODO-architecture.md
- eval-ground-truth.md
- changelog.md

Validation: {any gaps found}
```

---

## Implementation Notes

- Use the Agent tool with subagent_type=Explore to parallelize reading across independent code areas (e.g., read DB code, API code, and agent code simultaneously)
- For large agent instruction strings, use Read tool with specific line ranges rather than grepping
- The prompt-catalog.md will be the largest file — include full prompts, not summaries
- When extracting from Python code, look for `instruction="""..."""` patterns in LlmAgent constructors
- For API routes, check both the decorator path AND the router prefix from main.py to get the full path
- All docs should use GitHub-flavored markdown tables for consistency
