---
name: hephae-audit-code
description: Broad code quality audit — dead code detection, folder nesting depth, API design patterns, database access patterns, import cycles, unused exports, and file organization. Produces actionable findings.
argument-hint: [area | all]
---

# Code Quality Auditor

You are a senior software engineer auditing the Hephae Forge monorepo for code quality, organization, and maintainability. Your job is to find dead code, deep nesting, inconsistent patterns, and design issues.

**Output:** Findings report with file:line references, severity, and concrete refactor suggestions.

## Input

- No args or `all` → audit everything
- `api` → audit API layer only (routers, middleware, config)
- `agents` → audit agent code only
- `db` → audit database access layer
- `structure` → audit folder structure and file organization only
- `dead-code` → focus on dead code detection
- `imports` → focus on import cycles and unused imports

Arguments: $ARGUMENTS

---

## PHASE 1: STRUCTURAL AUDIT

### 1a. Folder Depth Analysis

Scan the directory tree and flag any path with >3 levels of nesting within a package:

```bash
find agents/hephae_agents -type f -name "*.py" | awk -F/ '{print NF-1, $0}' | sort -rn | head -20
find apps/api/hephae_api -type f -name "*.py" | awk -F/ '{print NF-1, $0}' | sort -rn | head -20
find lib -type f -name "*.py" | awk -F/ '{print NF-1, $0}' | sort -rn | head -20
```

Flag files at depth >5 from repo root.

### 1b. File Size Audit

Find oversized files (>500 lines suggest need for splitting):

```bash
find . -name "*.py" -not -path "*/node_modules/*" -not -path "*/.venv/*" | xargs wc -l | sort -rn | head -20
```

### 1c. Empty/Stub Files

```bash
find . -name "*.py" -not -path "*/node_modules/*" -size -50c | head -20
```

### 1d. Mixed Concerns

Check if files are doing too many things:
- Router files that contain business logic (should be in workflows/)
- Agent files that access Firestore directly (should go through lib/db/)
- Workflow files that define LlmAgents (should be in agents/)

---

## PHASE 2: DEAD CODE DETECTION

### 2a. Unused Imports

For key files, check if imported names are actually used:
```bash
# Find imports that might be unused
grep -rn "^from .* import" apps/api/hephae_api/ --include="*.py" | head -50
```

### 2b. Unreferenced Functions

Find functions defined but never called from outside their module:
```bash
# Find all function definitions
grep -rn "^def \|^async def " agents/ apps/ lib/ --include="*.py" | grep -v "__" | grep -v "test_"
```

Cross-reference with usages across the codebase.

### 2c. Stale Files

Check for files that haven't been imported by anything:
```bash
# List all .py files, then check which are imported
find agents/hephae_agents -name "*.py" -not -name "__init__.py" | while read f; do
  module=$(echo "$f" | sed 's|/|.|g' | sed 's|\.py$||')
  count=$(grep -r "$module\|$(basename $f .py)" agents/ apps/ lib/ --include="*.py" -l 2>/dev/null | wc -l)
  if [ "$count" -le 1 ]; then
    echo "ORPHAN: $f (referenced by $count files)"
  fi
done
```

### 2d. Commented-Out Code

```bash
grep -rn "^#.*def \|^#.*class \|^#.*import \|^# TODO\|^# FIXME\|^# HACK" agents/ apps/ lib/ --include="*.py" | head -30
```

---

## PHASE 3: API DESIGN AUDIT

### 3a. Route Consistency

Check all routers for consistent patterns:
- Do all admin routes use `verify_admin_request`?
- Do all routes have docstrings?
- Are response shapes consistent (e.g., always `{"success": bool, ...}`)?
- Are error responses standardized?

### 3b. Request/Response Models

- Are Pydantic models used for request bodies? (vs raw dict)
- Are response models typed? (vs returning raw dicts)
- Are optional fields explicitly marked Optional?

### 3c. Auth Patterns

- Any routes missing auth that should have it?
- Any internal-only routes (Cloud Tasks callbacks) accidentally exposed?
- Is CRON_SECRET checked consistently across all cron endpoints?

### 3d. Error Handling

- Are exceptions caught and returned as proper HTTP responses?
- Are 500 errors logged with context?
- Are client errors (400/404) distinguishable from server errors (500)?

---

## PHASE 4: DATABASE DESIGN AUDIT

### 4a. Firestore Patterns

Check all Firestore access code for:
- **Growing arrays** — any code doing `arrayUnion` or appending to arrays? (violates CLAUDE.md rule)
- **Blobs in Firestore** — any base64 data being stored? (should be in GCS)
- **set() vs update()** — is `set(merge=True)` used for existing docs? (should use `update()` with dotted paths)
- **Missing zipCode** — is `zipCode` always a top-level field? (CLAUDE.md rule)
- **Transactions** — are multi-document writes wrapped in transactions where needed?

### 4b. BigQuery Patterns

- Are INSERTs using parameterized queries?
- Is data that should be in BQ (historical) staying in Firestore?
- Are table schemas documented?

### 4c. Query Efficiency

- Any queries without proper indexes?
- Any queries fetching all documents when a filter would work?
- Any N+1 patterns (fetching in a loop instead of batching)?

---

## PHASE 5: IMPORT & DEPENDENCY AUDIT

### 5a. Circular Imports

Check for circular dependencies between packages:
```
agents → lib/db (OK)
agents → apps/api (VIOLATION — agents should not import from api)
lib/db → lib/common (OK)
lib/db → agents (VIOLATION — db should not import agents)
```

### 5b. Lazy Import Abuse

Check for excessive lazy imports (`from X import Y` inside functions):
- Legitimate: avoiding circular imports at module level
- Abuse: performance workaround masking a real dependency issue

### 5c. Dependency Graph Violations

Verify the declared dependency graph from CLAUDE.md:
```
apps/api → hephae-agents, hephae-db, hephae-integrations, hephae-common
hephae-agents → hephae-integrations, hephae-db, hephae-common
hephae-integrations → hephae-common
hephae-db → hephae-common
hephae-common → (external only)
```

Any import that violates this graph is a finding.

---

## PHASE 6: CODE QUALITY CHECKS

### 6a. Function Length

Flag functions >50 lines (likely need splitting).

### 6b. Exception Handling

- Bare `except:` or `except Exception:` without logging
- Swallowed exceptions (catch + pass)
- Exception handlers that return success (masking failures)

### 6c. Hardcoded Values

- Hardcoded URLs, API keys, or secrets
- Magic numbers without named constants
- Hardcoded business logic that should be configurable

### 6d. Type Safety

- Functions missing return type annotations
- Dict[str, Any] used where a Pydantic model would be better
- Unchecked `.get()` chains that could return None

---

## PHASE 7: REPORT

Write to `.claude/findings/code-audit.md`:

```markdown
# Code Quality Audit
Generated: {date}
Scope: {all | specific area}

## Summary
| Category | Issues Found | Critical | High | Medium | Low |
|----------|-------------|----------|------|--------|-----|
| Structure | | | | | |
| Dead Code | | | | | |
| API Design | | | | | |
| Database | | | | | |
| Imports | | | | | |
| Code Quality | | | | | |

## Findings
### FINDING-{N}: {title} [{severity}]
- **File:** `{path}:{line}`
- **Category:** {structure|dead-code|api|database|imports|quality}
- **Issue:** {what's wrong}
- **Fix:** {specific action}
- **Impact:** {what improves}

## Top 10 Recommendations
{ranked by impact × effort}
```

---

## Key Patterns to Know

The Hephae codebase follows these conventions (from CLAUDE.md):
- No blobs in Firestore — binary → GCS, store URL only
- zipCode is always top-level
- No growing arrays in Firestore — historical data → BigQuery
- update() with dotted paths for nested fields
- Agents are stateless: runner.py takes identity → returns report
- Capabilities are direct Python imports, not HTTP calls

## What NOT To Do

- Do NOT modify any code. Read-only audit.
- Do NOT flag style preferences (tabs vs spaces, quote style). Focus on functional issues.
- Do NOT flag test files as "dead code."
- Do NOT recommend rewrites of working code without a clear quality issue.
- Do NOT audit node_modules/, .venv/, or generated files.
