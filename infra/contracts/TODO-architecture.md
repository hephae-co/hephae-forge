# Architectural TODO — ADK-Native Improvements

> Priority order. Each item maps to a Google ADK feature that replaces custom infrastructure.

---

## 1. Universal `on_model_error_callback`

**Status**: DONE (2026-03-12) — fixed last 2 missing agents (chat.py, enrichment.py WebsiteFinder)
**Effort**: Small (1-2 hours)
**Impact**: High — eliminates silent agent failures from 429/503/529 errors

**What**: Add `on_model_error_callback` to every `LlmAgent` definition. On transient errors, retry with a fallback model.

**ADK Feature**: `LlmAgent(on_model_error_callback=...)` — native retry hook.

**Implementation**:
```python
# hephae_common/adk_helpers.py
from google.adk.agents import LlmAgent
from google.genai import types as genai_types

FALLBACK_MAP = {
    "gemini-2.5-flash": "gemini-2.0-flash",
    "gemini-2.0-flash": "gemini-2.0-flash-lite",
}

def model_error_handler(callback_context, llm_request, error):
    current = callback_context.agent.model
    fallback = FALLBACK_MAP.get(current)
    if fallback and isinstance(error, genai_types.ClientError):
        callback_context.agent.model = fallback
        return  # ADK retries automatically
    raise error
```

Then add to every agent:
```python
LlmAgent(
    ...,
    on_model_error_callback=model_error_handler,
)
```

**Files**: All agent definitions in `packages/capabilities/`, `backend/workflows/agents/`

---

## 2. Complete `output_schema` Migration

**Status**: Sprint 2 in progress — 12 agents migrated (added SocialMediaAuditOutput), ~15+ remaining
**Effort**: Medium (half day)
**Impact**: High — eliminates JSON parsing errors across remaining agents

**What**: Migrate all remaining agents from manual JSON parsing (`_safe_parse`, markdown fence stripping) to ADK's native `output_schema` parameter.

**ADK Feature**: `LlmAgent(output_schema=PydanticModel)` — Gemini validates response structure.

**Remaining agents** (non-exhaustive):
- Discovery sub-agents: `ContactAgent`, `SocialMediaAgent`, `CompetitorsAgent`, `MenuAgent`, `ChallengesAgent`, `NewsAgent`, `EntityMatcherAgent`
- Capability runners: SEO, Traffic, Competitive, Margin, Social
- Workflow agents: Dispatcher, Insights

**Files**: `packages/db/hephae_db/schemas/agent_outputs.py` (add models), each agent file

---

## 3. Composite Agent Rewrites (Competitive, Margin, Social)

**Status**: Not started
**Effort**: Large (2-3 days)
**Impact**: High — replaces custom asyncio orchestration with declarative ADK agents

**What**: Rewrite capability runners as ADK composite agents using `SequentialAgent`, `ParallelAgent`, and `output_key`.

**ADK Features**:
- `SequentialAgent(sub_agents=[...])` — ordered pipeline
- `ParallelAgent(sub_agents=[...])` — concurrent execution
- `output_key` — each sub-agent writes to `session.state[key]`
- Dynamic instructions via `lambda ctx: f"Use {ctx.state['key']}"`

**Example** (Competitive Analysis):
```python
competitive_pipeline = SequentialAgent(
    name="CompetitiveAnalysis",
    sub_agents=[
        ParallelAgent(
            name="DataGathering",
            sub_agents=[
                competitor_research_agent,   # output_key="competitor_profiles"
                market_position_agent,       # output_key="market_position"
                pricing_comparison_agent,    # output_key="pricing_data"
            ],
        ),
        synthesis_agent,  # reads all 3 keys, output_key="competitive_report"
    ],
)
```

**Files**: `packages/capabilities/hephae_agents/{competitive,margin_surgeon,social}/`

---

## 4. Standardize FirestoreSessionService

**Status**: DONE (2026-03-12) — all 5 runners accept optional session_service param; _run_workflow_analyze passes FirestoreSessionService
**Effort**: Small (2-3 hours)
**Impact**: Medium — enables post-mortem debugging of failed agent runs

**What**: Replace `InMemorySessionService` with `FirestoreSessionService` in all capability runners that execute via Cloud Tasks. Session state persists even if the task crashes.

**ADK Feature**: `from google.adk.sessions import FirestoreSessionService` (or custom `hephae_db.firestore.session_service.FirestoreSessionService`)

**Files**: All `runner.py` files in `packages/capabilities/`

---

## 5. Session ID in Task Metadata

**Status**: DONE (2026-03-12) — sessionPrefix stored in task metadata at workflow start
**Effort**: Tiny (30 min)
**Impact**: Medium — connects Cloud Task to ADK session for debugging

**What**: When a capability runner creates a session, store the `session_id` in the Firestore task document's metadata. This lets you trace: task → session → agent turns → model calls.

**Implementation**:
```python
# In _run_workflow_analyze or each runner
session_id = f"cap-{slug}-{cap_name}-{int(time.time())}"
await update_task(task_id, {"metadata.sessionId": session_id})
```

**Files**: `apps/api/backend/routers/admin/tasks.py`, capability runners

---

## 6. Webhook Callback (Replace Polling Loop)

**Status**: Not started
**Effort**: Medium (half day)
**Impact**: High — eliminates polling loop, stuck task detection, timeout issues

**What**: Instead of the workflow polling Firestore every 3s to check if Cloud Tasks finished, have each Cloud Task POST a webhook when it completes. The workflow uses `asyncio.Event` per business to await completion.

**Current flow** (polling):
```
Workflow → enqueue Cloud Tasks → poll Firestore every 3s → detect terminal status
```

**New flow** (webhook):
```
Workflow → enqueue Cloud Tasks → await asyncio.Event per business
Cloud Task completes → POST /api/internal/task-callback → set event
```

**Implementation**:
```python
# New endpoint: backend/routers/internal/task_callback.py
@router.post("/api/internal/task-callback")
async def task_callback(req: TaskCallbackRequest):
    # Signal the waiting workflow
    event = _pending_events.get(req.task_id)
    if event:
        event.set()

# In analysis.py — replace polling loop
events = {}
for task_id in task_ids:
    events[task_id] = asyncio.Event()
    _pending_events[task_id] = events[task_id]

await asyncio.gather(*[e.wait() for e in events.values()])
```

**Caveat**: Only works if workflow and callback run in the same Cloud Run instance. If Cloud Run scales to multiple instances, need Redis/Pub-Sub or Firestore watch instead. For `min-instances=1, max-instances=5`, consider Firestore `.on_snapshot()` as alternative.

**Files**: New `backend/routers/internal/task_callback.py`, `backend/workflows/phases/analysis.py`, `backend/routers/admin/tasks.py`

---

## 7. BusinessAnalysisPipeline as SequentialAgent

**Status**: Not started
**Effort**: Large (2-3 days)
**Impact**: High — replaces `_run_workflow_analyze` (180 lines of imperative code) with declarative ADK pipeline

**What**: Model the entire business analysis pipeline as a single ADK `SequentialAgent`:

```
SequentialAgent("BusinessAnalysisPipeline", sub_agents=[
    enrichment_agent,           # output_key="enriched_identity"
    research_context_agent,     # output_key="research_context"
    ParallelAgent("Capabilities", sub_agents=[
        seo_agent,              # output_key="seo_report"
        traffic_agent,          # output_key="traffic_forecast"
        competitive_agent,      # output_key="competitive_report"
        social_agent,           # output_key="social_audit"
    ]),
    insights_agent,             # reads all outputs, output_key="insights"
])
```

**Benefits**:
- ADK manages execution order, parallelism, error handling
- Session state is the single source of truth
- Each agent reads predecessors' output via `context.state`
- `on_model_error_callback` covers every agent automatically

**Depends on**: Items 1, 3, 4

**Files**: New `packages/capabilities/hephae_agents/pipeline.py`, refactor `backend/routers/admin/tasks.py`

---

## 8. Eval Coverage Expansion

**Status**: Partial (8 eval cases exist for research agents + 4 for outreach)
**Effort**: Medium-Large (ongoing)
**Impact**: Medium — catches regressions, validates prompt changes

**What**: Build comprehensive eval suites using ADK's `EvalSet`/`EvalCase` framework:

1. **Structural evals**: Does each agent's output match its `output_schema`? (automated)
2. **Quality evals**: Are social links valid URLs? Do competitors exist? Is the SEO report actionable?
3. **Regression evals**: Golden fixtures from production runs — compare new outputs against known-good baselines
4. **Pipeline evals**: End-to-end test of `BusinessAnalysisPipeline` for 5 fixture businesses

**ADK Feature**: `google.adk.evaluation.EvalSet`, `EvalCase`, `AgentEvaluator`

**Files**: `tests/evals/`, `contracts/eval-standards.md`

---

## Priority Matrix

| # | Item | Effort | Impact | Depends On | Status |
|---|------|--------|--------|------------|--------|
| 1 | Model error callback | Small | High | — | DONE |
| 5 | Session ID in metadata | Tiny | Medium | — | DONE |
| 2 | output_schema migration | Medium | High | — | In Progress (12/25+) |
| 4 | FirestoreSessionService | Small | Medium | — | DONE |
| 6 | Webhook callback | Medium | High | — | Not Started |
| 3 | Composite agent rewrites | Large | High | 1, 2 | Not Started |
| 7 | Pipeline SequentialAgent | Large | High | 1, 3, 4 | Not Started |
| 8 | Eval expansion | Ongoing | Medium | 2 | Not Started |

---

## Workflow Observations — Live Run `Buka21SVb4U4aHPOVHZf` (2026-03-13)

> Workflow: 29 Restaurants in 07110 (Nutley, NJ). Observed in real-time during analysis phase.

### Issue 9: 20/29 Businesses Complete Analysis with ZERO Capabilities

**Status**: Not started
**Effort**: Medium (half day)
**Impact**: Critical — 69% of businesses produce no useful output

**Problem**: When a business has no `officialUrl` (20/29 in this run), the capability gating in `registry.py` skips SEO (needs URL), competitive (needs `competitors`), and margin (needs `menuScreenshotBase64`). Traffic and social should run (no gating), but 20 businesses still ended up with `capabilitiesCompleted: []`. The task completes "successfully" with zero work done.

**Root causes**:
1. **No early exit or warning** — `_run_workflow_analyze` in `tasks.py:290-302` filters caps via `should_run`, but if all are skipped (or traffic/social fail silently), it returns `STATUS_COMPLETED` with empty lists. No error, no flag.
2. **Only 9/29 businesses had URLs** — enrichment's `_find_website()` fails frequently for small local restaurants (search-based fallback often returns nothing).
3. **Traffic and social should be URL-independent** — but they may be failing or being skipped by some other mechanism when there's no enriched profile data.

**Fix ideas**:
- Add minimum-capability threshold: if `len(caps_to_run) < 2`, flag the business as `ANALYSIS_SKIPPED` instead of `analysis_done`
- Make traffic forecast and social audit truly work without URLs — they only need name + address + zip
- Log a WARNING when 0 capabilities are eligible, include business name + what's missing
- Evaluate whether these no-URL businesses should even proceed past enrichment

**Files**: `apps/api/backend/routers/admin/tasks.py:290-387`, `apps/api/backend/workflows/capabilities/registry.py:170-218`

---

### Issue 10: Massive Gemini 429 Rate Limiting (RESOURCE_EXHAUSTED)

**Status**: Partially mitigated (fallback works), but needs rate-limiting strategy
**Effort**: Medium
**Impact**: High — slows entire workflow, burns fallback model quota

**Problem**: With 29 businesses enqueued as Cloud Tasks simultaneously (all within 3 seconds at 21:21:34-37), the `maxConcurrentDispatches: 3` queue config means 3 tasks run in parallel. Each task fires multiple Gemini API calls (discovery, enrichment, social, SEO, traffic, competitive). The combined load triggers constant 429s on `gemini-3.1-flash-lite-preview`.

**Observed behavior**:
- Dozens of 429 fallbacks from `gemini-3.1-flash-lite-preview` → `gemini-2.5-flash-lite` per minute
- Fallback model succeeds but is slower/more expensive
- No backoff between retries — model_fallback immediately retries on the fallback model

**Fix ideas**:
- Add exponential backoff with jitter before retrying on fallback model (not just immediate switch)
- Consider reducing `maxConcurrentDispatches` to 2 for large batches, or dynamically adjusting based on batch size
- Add a pre-flight rate budget: if batch > 15 businesses, stagger task scheduling with 5-10s delays
- Track 429 count per workflow and surface in admin UI as a health metric

**Files**: `hephae_common/model_fallback.py`, Cloud Tasks queue config

---

### Issue 11: Social Audit Native JSON Parse Fails 100% of the Time

**Status**: Not started
**Effort**: Small (1-2 hours)
**Impact**: Medium — fallback extraction works but adds latency and fragility

**Problem**: Every single social audit in this run logged `Native JSON parse failed, attempting fallback extraction`. The native `output_schema` or `response_schema` is not working for the social media auditor — it always falls back to manual extraction.

**Observed**: 6/6 social audit runs showed this warning, all recovered via fallback but this is a reliability risk.

**Fix**: Investigate why the social audit agent's structured output isn't producing valid JSON. Likely a schema mismatch or the agent returning markdown-wrapped JSON despite `output_schema`.

**Files**: `packages/capabilities/hephae_agents/social/media_auditor/runner.py`

---

### Issue 12: BLS API Key Invalid ("placeholder")

**Status**: Not started
**Effort**: Tiny (config fix)
**Impact**: Medium — traffic forecasts missing labor/economic data

**Problem**: BLS API calls fail with `The key:placeholder provided by the User is invalid`. The `BLS_API_KEY` env var on Cloud Run is set to a placeholder value.

**Fix**: Set a valid BLS API key in Cloud Run environment variables.

**Files**: `apps/api/backend/config.py` (env var), Cloud Run service config

---

### Issue 13: PageSpeed API Rate Limiting

**Status**: Not started
**Effort**: Small
**Impact**: Low-Medium — SEO audits delayed but eventually succeed

**Problem**: PageSpeed API returns 429 for concurrent requests. The SEO runner retries 3 times with 5s/15s/30s backoff, which works but adds ~50s latency per business. With 3 concurrent tasks all hitting PageSpeed, rate limits are easily triggered.

**Observed**: Multiple businesses (theoakleykitchen.com, seamless.com/bosphorus) hit all 3 retries.

**Fix ideas**:
- Add a semaphore or rate limiter for PageSpeed calls (max 1 concurrent across all tasks)
- Cache PageSpeed results per domain (don't re-check on resume/retry)
- Consider if PageSpeed for Seamless/aggregator URLs is even useful (Bosphorus had its Seamless page tested instead of thebosphorus.us)

**Files**: `packages/capabilities/hephae_agents/seo_auditor/tools.py`

---

### Issue 14: SEO Auditor Testing Wrong URLs (Aggregator Pages)

**Status**: Not started
**Effort**: Small-Medium
**Impact**: Medium — SEO reports are meaningless if they audit Seamless/Grubhub instead of the actual business site

**Problem**: The Bosphorus has `officialUrl: https://thebosphorus.us` but the SEO runner tested `https://www.seamless.com/menu/the-bosphorus-226-franklin-ave-nutley/...` — a third-party aggregator page. PageSpeed scores and SEO analysis for Seamless are irrelevant to the business.

**Fix**: Validate that the URL being audited matches the business's own domain, not a marketplace/aggregator. Skip or flag if the URL is from seamless.com, grubhub.com, doordash.com, ubereats.com, yelp.com, etc.

**Files**: `packages/capabilities/hephae_agents/seo_auditor/runner.py`

---

### Issue 15: Agents Hallucinating Competitor Names from Other Cities

**Status**: Not started
**Effort**: Medium
**Impact**: Medium — wasted API calls, incorrect competitive analysis

**Problem**: Google search logs show the agents searching for completely unrelated businesses in other cities: "The Fireplace" Brookline MA, "Joe's Stone Crab" Miami Beach, "The Flying Burrito", "The French Pantry" Jacksonville, "The Baked Bear" San Francisco, "The Melting Pot", "Ad Hoc" Yountville. These are NOT competitors in Nutley, NJ 07110.

**Root cause**: The competitive analysis agent is hallucinating well-known restaurants as competitors instead of finding actual local competitors. The prompt likely needs stronger geographic constraints.

**Fix**: Tighten competitive analysis prompts to strictly scope to the same zip code/city. Add post-generation validation that competitor addresses are in the target area.

**Files**: `packages/capabilities/hephae_agents/competitive/` agent prompts

---

### Issue 16: Enrichment Website Search Fails Silently for Many Businesses

**Status**: Not started
**Effort**: Medium
**Impact**: High — cascading effect, businesses without URLs get 0 capabilities

**Problem**: 20/29 businesses ended up with no `officialUrl`. The enrichment phase's `_find_website()` uses a search-based fallback when no URL is found in discovery, but it fails with empty results for most small local restaurants (logged as `Website search failed for X:`  with empty error message).

**Observed**: The Old Canal Inn, MEAL, Bella Luce all went through search fallback and got nothing.

**Fix ideas**:
- Improve the WebsiteFinderAgent to try multiple search strategies (Google Maps URL, Yelp page as proxy)
- If no official site exists, use the Google Maps/Places listing URL as a proxy `officialUrl`
- Consider: should capabilities be gated on URL at all? Traffic and social don't need one.

**Files**: `apps/api/backend/workflows/phases/enrichment.py:28-45`

---

### Updated Priority Matrix

| # | Item | Effort | Impact | Depends On | Status |
|---|------|--------|--------|------------|--------|
| 1 | Model error callback | Small | High | — | DONE |
| 5 | Session ID in metadata | Tiny | Medium | — | DONE |
| 2 | output_schema migration | Medium | High | — | In Progress (12/25+) |
| 4 | FirestoreSessionService | Small | Medium | — | DONE |
| **9** | **Zero-cap analysis completion** | **Medium** | **Critical** | — | **Not Started** |
| **16** | **Enrichment website search** | **Medium** | **High** | — | **Not Started** |
| **11** | **Social audit JSON parse** | **Small** | **Medium** | 2 | **Not Started** |
| **14** | **SEO auditing wrong URLs** | **Small-Medium** | **Medium** | — | **Not Started** |
| **15** | **Competitor hallucination** | **Medium** | **Medium** | — | **Not Started** |
| **12** | **BLS API key placeholder** | **Tiny** | **Medium** | — | **Not Started** |
| 6 | Webhook callback | Medium | High | — | Not Started |
| **10** | **Gemini 429 rate strategy** | **Medium** | **High** | — | **Not Started** |
| **13** | **PageSpeed rate limiting** | **Small** | **Low-Medium** | — | **Not Started** |
| 3 | Composite agent rewrites | Large | High | 1, 2 | Not Started |
| 7 | Pipeline SequentialAgent | Large | High | 1, 3, 4 | Not Started |
| 8 | Eval expansion | Ongoing | Medium | 2 | Not Started |
