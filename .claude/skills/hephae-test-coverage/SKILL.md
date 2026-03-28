---
name: hephae-test-coverage
description: Test coverage audit — detects mock-based tests, missing ADK evals, missing functional markers, dead/redundant tests, and critical behavioral gaps. Produces a prioritized plan for real functional test coverage.
argument-hint: [all | agents | api | workflows | integration | evals | frontend | mocks]
user_invocable: true
---

# Test Coverage Auditor

You are a test quality engineer for Hephae. Your job is to audit the existing test suite for mock-based tests, missing ADK evals, missing functional markers, dead/redundant tests, and meaningful coverage gaps. Produce a prioritized plan for new real functional tests.

**Policy:** Hephae tests must be real functional tests — no mocks of internal code. Every agent must have an ADK eval. Every test that calls a runner or Gemini must be marked `@pytest.mark.functional`.

**Output:** A findings report written to `.claude/findings/test-coverage.md` with specific file:line references and a gap-first prioritized test plan.

## Input

| Arg | Scope |
|-----|-------|
| `all` or empty | Full audit across all layers |
| `agents` | `tests/agents/` — unit tests for agent config + tools |
| `api` | `tests/api/` — API route tests |
| `workflows` | `tests/workflows/` — workflow pipeline tests |
| `integration` | `tests/integration/` — live API integration tests |
| `evals` | `tests/evals/` — ADK agent eval tests |
| `frontend` | `apps/web/src/**/*.test.*` — frontend unit tests |
| `mocks` | Scan ALL test files for mock usage only |

Arguments: $ARGUMENTS

---

## PHASE 0: MOCK + QUALITY SCAN (always run first)

**This phase runs regardless of scope argument.** Grep all test files for banned patterns before any other analysis.

### 0a. Mock Usage Detection

Scan every file under `tests/` for these banned imports and patterns:

```
Banned imports:
  from unittest.mock import ...
  from unittest import mock
  import unittest.mock
  from pytest_mock import ...
  from asynctest import ...

Banned patterns:
  MagicMock
  AsyncMock
  patch(
  @patch(
  mocker.patch
  mocker.Mock
  ASGITransport
  AsyncClient(app=
  TestClient(app=   ← OK for pure sync integration only — flag as REVIEW
```

For each file with any banned pattern, record:
- **File path**
- **Line number** of each occurrence
- **Pattern found**
- **Severity:**
  - `CRITICAL` — mocking an internal runner, agent, or DB function (masks real behavior)
  - `HIGH` — mocking external HTTP calls that should use real fixtures/recordings
  - `MEDIUM` — `TestClient(app=` for sync integration tests (acceptable but flag for review)
  - `LOW` — mocking OS/env/time (acceptable in isolated logic tests)

### 0b. Missing `@pytest.mark.functional` Marker

Scan `tests/` for test functions that call runner functions or import from `hephae_agents.*` but are NOT marked `@pytest.mark.functional`:

```
Patterns that indicate a functional test:
  from hephae_agents.
  import hephae_agents.
  run_seo_audit
  run_competitive_analysis
  run_traffic_forecast
  run_margin_analysis
  run_business_overview
  run_marketing_pipeline
  run_social_media_audit
  AgentEvaluator
  Runner(
  InMemorySessionService
```

Flag any test function matching these patterns that lacks `@pytest.mark.functional` or `pytestmark = pytest.mark.functional`.

### 0c. Missing `@pytest.mark.integration` Marker

Scan `tests/` for test functions that call Firestore/BigQuery/GCS functions but are NOT marked `@pytest.mark.integration`:

```
Patterns that indicate integration test:
  from hephae_db.
  import hephae_db.
  firestore
  bigquery
  get_registered_zipcode
  list_registered
  get_pulse_job
```

Flag any test function matching these patterns that lacks `@pytest.mark.integration`.

### 0d. Credential Guard Check

Every test file that uses `@pytest.mark.functional` or `@pytest.mark.integration` must have one of:
- `pytestmark = pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), ...)`
- `pytestmark = pytest.mark.skipif(not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"), ...)`
- Or rely on `tests/conftest.py` auto-skip (check `conftest.py` for `pytest_collection_modifyitems` with functional/integration skip logic)

Flag files that call real APIs without a credential guard as **UNSAFE — will fail in CI**.

---

## PHASE 1: MAP THE TEST SUITE

### 1a. Enumerate all test files

Read every test file in scope. For each file, record:
- **Path** — `tests/agents/test_discovery_agents.py`
- **Layer** — `unit` / `functional` / `integration` / `eval` / `e2e`
  - `unit` — pure logic, no external calls, no API keys needed
  - `functional` — calls real runners/agents with Gemini API
  - `integration` — calls real Firestore/BigQuery/network
  - `eval` — ADK `AgentEvaluator.evaluate()` eval cases
  - `e2e` — full pipeline from input to Firestore write
- **Test type** — `real` (calls actual code) or `mock-based` (uses patch/Mock)
- **Test count** — number of `def test_` functions
- **Markers** — `@pytest.mark.functional`, `@pytest.mark.integration`, `@pytest.mark.asyncio`, etc.
- **Credential guard** — yes/no (has skipif for missing keys)

### 1b. Map test → production code

For each test file, identify what production module it covers and whether it tests behavior or just structure:

| Test File | Production Module | Coverage Type | Real or Mock? |
|-----------|------------------|---------------|---------------|
| example | example | Behavioral / Structural | Real / Mock |

### 1c. Identify untested production modules

Read `agents/hephae_agents/`, `apps/api/hephae_api/routers/`, `lib/` and compare against test coverage map. Flag modules with **zero test coverage**.

---

## PHASE 2: ADK EVAL COVERAGE AUDIT

This is a first-class check. Every production agent must have an ADK eval.

### 2a. List all production agents

Enumerate every directory under `agents/hephae_agents/` that contains an `agent.py` with a `root_agent` or agent object.

### 2b. List all existing ADK evals

For each directory under `tests/evals/`, check:
- Has `agent.py` that re-exports `root_agent` ✓/✗
- Has `eval.test.json` with at least 1 `eval_cases[]` entry ✓/✗
- Has `test_config.json` with `criteria.response_match_score` ✓/✗
- Is registered in `tests/evals/test_agent_evals.py` ✓/✗

### 2c. Cross-reference: agents missing evals

| Agent | Has eval dir? | Has eval.test.json? | Registered in test_agent_evals.py? | Gap |
|-------|--------------|---------------------|-------------------------------------|-----|
| seo_auditor | ✓ | ✓ | ✓ | OK |
| traffic_forecaster | ✓ | ✓ | ✓ | OK |
| ... | | | | |
| {missing_agent} | ✗ | ✗ | ✗ | CRITICAL |

### 2d. Eval quality check

For each existing `eval.test.json`:
- Does it have at least 2 eval cases? (single case = low confidence)
- Does `final_response` contain substantive expected content? (not just "provide marketing content" — that's too vague to catch regressions)
- Does `intermediate_data.tool_uses` verify the agent used the right tools?
- Is `session_input.state` seeded with realistic data the agent needs?

Flag:
- Evals with 1 case as **LOW CONFIDENCE — add more cases**
- Evals with generic `final_response` as **WEAK ASSERTION — strengthen expected output**
- Evals that don't check `tool_uses` as **INCOMPLETE — add tool verification**

---

## PHASE 3: DEAD + REDUNDANT TEST DETECTION

For each test, apply these checks:

### Check 1: Tests that only verify object construction
Flag tests like:
```python
def test_agent_name(self):
    assert news_agent.name == "NewsAgent"
```
Mark as **LOW VALUE — structural only**.

### Check 2: Duplicate coverage
Flag test files where two or more tests exercise the exact same code path with identical fixtures.

### Check 3: Tests for deleted/renamed modules
Check if any test imports a module that no longer exists. Flag as **DEAD — stale import**.

### Check 4: Tests with no assertions
Flag test functions that have no `assert` statement.

### Check 5: Eval tests for agents that no longer exist
Cross-reference `tests/evals/*/agent.py` files against `agents/hephae_agents/` — if the agent under test was removed, the eval is dead.

### Check 6: Overlapping integration + unit tests
Flag cases where both a unit test AND an integration test cover the exact same narrow behavior.

---

## PHASE 4: CRITICAL GAP ANALYSIS

Map every major production capability against test coverage. Flag anything with no meaningful behavioral test (structural-only or mock-based tests don't count):

### 4a. Agent pipeline gaps

For each pipeline, determine if there is a **real** behavioral test (functional runner call or ADK eval — mocked runner calls do NOT count):

| Pipeline | Has Real Behavioral Test? | Test Type | Gap |
|----------|--------------------------|-----------|-----|
| Discovery pipeline | ✓ integration | Runner | OK |
| Pulse orchestrator | ? | | |
| Industry pulse | ? | | |
| Traffic forecaster | ? | | |
| SEO auditor | ? | | |
| Competitive analysis | ? | | |
| Margin surgeon | ? | | |
| Marketing swarm | ? | | |
| Reference harvester | ? | | |
| Tech intelligence | ? | | |

### 4b. API route gaps

Read every router file in `apps/api/hephae_api/routers/web/` and `routers/batch/`. For each route, check if there's a **real** test (not mock-based) in `tests/api/`. Flag uncovered routes.

Key routes to check:
- `POST /api/overview` — business overview
- `GET /api/cron/weekly-pulse` — pulse cron
- `GET /api/cron/industry-pulse` — industry pulse cron
- `GET /api/cron/reference-harvest` — reference harvest cron
- `POST /api/workflows` — workflow creation
- `GET /api/pulse/:zipCode` — pulse retrieval
- `POST /api/b/save` — business profile save

### 4c. Firestore schema gaps

Read `lib/db/hephae_db/firestore/`. For each collection module, check if `tests/db/` has a **real** (non-mocked) schema consistency test.

### 4d. Auth + middleware gaps

Check if HMAC signing, Firebase token validation, and cron secret auth have **real** tests covering:
- Valid token → passes
- Invalid token → 401
- Missing token → 401/403
- Expired token → 401

Note: these tests should call the real auth function directly, not mock the middleware.

### 4e. E2E workflow gaps (critical)

These flows need real end-to-end tests:
- Full happy path: business search → overview → capability run → eval pass
- Pulse cron → batch dispatch → pulse generation → Firestore write
- Heartbeat registration → scheduled check → email notification
- Discovery cron → batch → qualification → capability queue

### 4f. Frontend gaps

Check `apps/web/src/` for test files. Flag:
- `apiFetch` / auth token forwarding — no test
- `triggerBusinessOverview` flow — no test
- `MapVisualizer` rendering — no test
- Error boundary / fallback states — no test

---

## PHASE 5: PRIORITIZED TEST PLAN

Produce a prioritized list of NEW tests to write, ordered by impact. All recommended tests must be real functional tests — no mocks.

### Priority: CRITICAL (blocks production confidence)

For each critical gap, specify:
```
TEST: {name}
File: tests/{layer}/{filename}.py
Type: functional / integration / eval
What it tests: {one sentence}
Why critical: {reason — catches what class of regression?}
Implementation: call {specific runner/function} with {fixture}, assert {business validation}
Estimated effort: {S/M/L}
```

Focus on:
1. **Missing ADK evals** — each agent without an eval is a blind spot
2. **E2E happy path** — single business through full pipeline
3. **Cron → batch → result** — weekly pulse produces a valid Firestore document
4. **API auth** — every auth mechanism has a negative test (real crypto, not mocked)
5. **Agent output schema** — each agent's `output_schema` Pydantic model validates real output

### Priority: HIGH (catches frequent regressions)

Focus on:
- Runner functions: does `run_seo_audit(identity)` return the right shape with real data?
- Eval thresholds: are score gates still meaningful?
- Firestore write consistency: schema fields match contracts

### Priority: MEDIUM (coverage depth)

Focus on:
- Edge cases: empty business name, missing coordinates, API key missing
- Error paths: tool failure propagation, model fallback triggering

### Priority: LOW (nice to have)

- Frontend component tests
- Load/perf tests
- Additional eval cases for existing evals

---

## PHASE 6: REPORT

Write to `.claude/findings/test-coverage.md`:

```markdown
# Test Coverage Audit
Generated: {date}
Scope: {scope}
Test files read: {count}
Total test functions: {count}
Mock-based tests found: {count}
ADK evals: {covered} / {total agents}

## Mock Usage (Phase 0)
{table: file | line | pattern | severity}
{count} files with mock usage — {count} CRITICAL, {count} HIGH, {count} MEDIUM, {count} LOW

## Missing Markers
{table: file | function | issue}

## ADK Eval Coverage (Phase 2)
{table: agent | has eval | has test.json | registered | quality issues}
Agents without evals: {list}

## Test Suite Summary

| Layer | Files | Tests | Mock-Based | Real/Functional | Evals | Dead/Redundant |
|-------|-------|-------|-----------|-----------------|-------|----------------|
| agents | | | | | | |
| api | | | | | | |
| workflows | | | | | | |
| integration | | | | | | |
| evals | | | | | | |
| frontend | | | | | | |

## Dead / Redundant Tests
{findings sorted by: DEAD > REDUNDANT > LOW VALUE}

## Critical Coverage Gaps
{gaps sorted by impact}

## Prioritized Test Plan
{CRITICAL → HIGH → MEDIUM → LOW}

## Quick Wins
{top 3 tests that are small effort + high impact — write these first}
```

---

## Key Files

| Area | Location |
|------|----------|
| All tests | `tests/` |
| Agent units | `tests/agents/` |
| API tests | `tests/api/` |
| Workflow tests | `tests/workflows/` |
| Integration tests | `tests/integration/` |
| ADK evals | `tests/evals/` |
| Frontend tests | `apps/web/src/**/*.test.*` |
| Test config | `tests/conftest.py`, `tests/integration/conftest.py` |
| Test fixtures | `tests/integration/businesses.py` |
| Eval runner | `tests/evals/test_agent_evals.py` |

## ADK Eval Structure Reference

Each agent eval lives at `tests/evals/{agent_name}/`:

```
tests/evals/{agent_name}/
├── agent.py          # re-exports production root_agent
├── eval.test.json    # eval cases (see format below)
└── test_config.json  # {"criteria": {"response_match_score": 0.3}}
```

`eval.test.json` format:
```json
{
  "eval_set_id": "{agent}_eval",
  "eval_cases": [{
    "eval_id": "{case_id}",
    "conversation": [{
      "invocation_id": "turn_1",
      "user_content": {"parts": [{"text": "...prompt..."}], "role": "user"},
      "final_response": {"parts": [{"text": "...expected content..."}], "role": "model"},
      "intermediate_data": {"tool_uses": [], "intermediate_responses": []}
    }],
    "session_input": {"app_name": "test", "user_id": "test_user", "state": {}}
  }]
}
```

## What NOT To Do

- Do NOT run tests — read-only analysis only.
- Do NOT write test code unless explicitly asked after the audit.
- Do NOT recommend mock-based tests — all recommended tests must be real functional tests.
- Do NOT flag structural config tests as dead if they catch import errors — only if they assert hardcoded literals with zero behavioral signal.
- Do NOT recommend rewriting working real tests — additive gaps only.
- Do NOT flag `@pytest.mark.integration` tests as redundant vs `@pytest.mark.functional` — they serve different purposes.
- Do NOT treat mock-based tests as covering a gap — if a runner is only tested via mocks, treat it as untested.
