# Weekly Pulse — Comprehensive Audit Findings

**Date**: 2026-03-19
**Scope**: Plan-vs-code review, local context gap plan review, ADK pattern audit, Firestore data validation
**Handoff to**: Coding agent

---

## Finding 1: Signal Archive Bug (P0 — Data Loss)

**Location**: `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py:254-263`
**Collection**: `pulse_signal_archive`

The `pulse_signal_archive` collection has **0 documents** despite 8+ pulse runs. The code path exists at line 254:

```python
if raw_signals:
    archive_sources = {}
    for source_name, data in raw_signals.items():
        if data:
            archive_sources[source_name] = {
                "raw": _truncate(data, 5000),
                "fetchedAt": datetime.utcnow().isoformat(),
                "version": "v1",
            }
    await save_signal_archive(zip_code, week_of, archive_sources, pre_computed)
```

**Root cause hypothesis**: `rawSignals` is empty in session state after pipeline completes. The `BaseLayerFetcher` writes it to state via `state_delta`, but by the time the orchestrator reads `final_state.get("rawSignals", {})`, it may be empty due to:
1. The state key being written differently than read (casing mismatch)
2. ADK state not propagating from nested agent to top-level session
3. The `_truncate()` call reducing data to nothing

**Action**: Add logging before the `if raw_signals:` check to print `final_state.keys()` and the actual value. Cross-reference with `BaseLayerFetcher`'s `state_delta` key names in `pulse_data_gatherer.py`.

---

## Finding 2: Stuck Job — No Timeout Mechanism (P1)

**Location**: `lib/db/hephae_db/firestore/pulse_jobs.py`, `apps/api/hephae_api/routers/admin/weekly_pulse.py`

One `pulse_jobs` document is stuck in RUNNING state indefinitely. There is no:
- Timeout mechanism (e.g., auto-fail after 10 minutes)
- Cleanup cron for stale jobs
- Health check on running jobs

**Action**:
1. Add a `timeoutAt` field when setting status to RUNNING (e.g., `utcnow() + timedelta(minutes=15)`)
2. In `get_pulse_job_status()`, check if `status == "RUNNING"` and `timeoutAt < utcnow()` — if so, mark as FAILED with error "Pipeline timeout"
3. Optionally: add a cleanup endpoint or cron that sweeps stale RUNNING jobs

---

## Finding 3: DualModelSynthesis Bypasses ADK Model Abstraction (P1 — Tech Debt)

**Location**: `agents/hephae_agents/research/pulse_orchestrator.py:64-228`

`DualModelSynthesis` is a proper `BaseAgent` but calls models directly instead of through ADK:

- **Claude**: Raw `httpx` POST to `api.anthropic.com/v1/messages` (lines ~140-180)
- **Gemini**: Direct `genai_client.generate_content()` via `hephae_common.gemini_client` (lines ~100-135)

ADK natively supports multi-model via `LiteLlm`:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

claude_synth = LlmAgent(
    name="ClaudeSynthesis",
    model=LiteLlm(model="anthropic/claude-sonnet-4-20250514"),
    instruction=SYNTHESIS_INSTRUCTION,
    output_schema=WeeklyPulseOutput,
    output_key="claudePulseOutput",
)

gemini_synth = LlmAgent(
    name="GeminiSynthesis",
    model="gemini-2.0-flash",
    instruction=SYNTHESIS_INSTRUCTION,
    output_schema=WeeklyPulseOutput,
    output_key="geminiPulseOutput",
)
```

Then wrap both in a `ParallelAgent` and keep the deterministic `_merge_insights()` as a follow-up `BaseAgent`.

**Benefits**:
- ADK handles retries, token counting, and error handling
- Consistent logging/tracing across both models
- No raw HTTP client management
- `output_schema` enforced natively for both models

**Action**: Refactor `DualModelSynthesis` into 3 sub-agents: `ParallelAgent([claude_synth, gemini_synth])` → `InsightMerger(BaseAgent)`. Keep the merge logic deterministic (Python, no LLM).

---

## Finding 4: Local Context Gap — Schema Changes Needed (P0 — Feature)

**Location**: `lib/db/hephae_db/schemas/agent_outputs.py` (line ~880), `weekly-pulse-local-context-plan.md`

**Problem validated by Firestore data**: The latest successful pulse run (5 insights, critiquePass=True) has 4/5 insights that are purely macro (BLS/Census number crunching). The pipeline captures rich local data (named venues like "Aromi Di Napoli", competitor names like "Luna Wood Fire Tavern", specific events with dates/addresses) but the synthesis LLM ignores it in favor of clean structured BLS numbers.

### 4a. New Schema Models

Add to `agent_outputs.py`:

```python
class LocalEvent(BaseModel):
    what: str          # "Italian Language Exchange at Aromi Di Napoli"
    where: str         # "246 Washington Ave"
    when: str          # "Saturday March 21, 10am"
    businessImpact: str  # "Foot traffic boost for morning hours on Washington Ave"
    source: str        # "NJBulletin.com via Social Pulse"

class CompetitorNote(BaseModel):
    business: str      # "Luna Wood Fire Tavern"
    observation: str   # "Shifting marketing to spring private event bookings"
    implication: str   # "Private event demand is rising — consider adding a catering page"
    source: str        # "Social Pulse research"

class LocalBriefing(BaseModel):
    thisWeekInTown: list[LocalEvent] = []
    competitorWatch: list[CompetitorNote] = []
    communityBuzz: str = ""
    governmentWatch: str = ""
```

Add `localBriefing: LocalBriefing | None = None` to `WeeklyPulseOutput`.

### 4b. Synthesis Prompt Update

**Location**: `agents/hephae_agents/research/weekly_pulse_agent.py` — `WEEKLY_PULSE_CORE_INSTRUCTION`

Add explicit instructions requiring the LLM to populate `localBriefing` from the `localReport` and `socialPulse` state keys. Include examples showing what good local events and competitor notes look like. Emphasize: `localBriefing` fields are REQUIRED — empty arrays only when genuinely no local data exists.

### 4c. DualModelSynthesis Combiner Update

**Location**: `pulse_orchestrator.py` — `_merge_insights()`

Update the merge logic to handle `localBriefing`:
- Events: deduplicate by venue+date, merge from both models
- Competitor notes: deduplicate by business name, keep the richer observation
- communityBuzz: pick the longer/more specific version
- governmentWatch: concatenate unique items

### 4d. Batch Processor Prompt Update

**Location**: `apps/api/hephae_api/workflows/orchestrators/pulse_batch_processor.py`

The batch processor's JSONL prompt (Stage 3) also needs the localBriefing schema and instructions. This is missing from the local context plan doc.

---

## Finding 5: Critique Agent Needs Local Quality Pass (P0 — Feature)

**Location**: `agents/hephae_agents/research/pulse_critique_agent.py`

The current critique only checks insight quality (obviousness < 30, actionability >= 70, data density >= 60). The local context plan proposes a two-pass critique:

**Pass A — Local Briefing Quality** (NEW):
- Are events specific? (must have venue name + date + address)
- Are competitor notes about NAMED businesses? (not "local restaurants")
- Is communityBuzz based on actual social data? (not generic filler)
- Is governmentWatch specific? (not "monitor your town website")

**Pass B — Insight Quality** (existing):
- Obviousness (< 30 to pass)
- Actionability (>= 70 to pass)
- Data density (>= 60 to pass)

**Missing from plan**: Specific score thresholds for Pass A. Define what scores trigger a localBriefing rewrite vs a full pulse rewrite.

**Action**: Update `PulseCritiqueAgent` instruction to include Pass A criteria. Update `CritiqueRouter` to route local-only failures to a localBriefing-specific rewrite (not full pulse rewrite).

---

## Finding 6: LocalScoutAgent Instruction Needs Structured Output (P1)

**Location**: `agents/hephae_agents/research/pulse_domain_experts.py` — `LocalScoutAgent`

Currently LocalScoutAgent produces a free-text `localReport` string. For the new `localBriefing` schema to work well, the LocalScoutAgent should be updated to output structured data that maps more directly to `LocalEvent[]` and `CompetitorNote[]`. This doesn't need to match the exact schema (the synthesis agent handles that), but the local report should explicitly separate:
- Events (with venue, date, address when available)
- Competitor observations (with business name)
- Community sentiment
- Government/regulatory items

**Action**: Update `_build_local_instruction()` to request structured sections in the output. Optionally add `output_schema` for a `LocalReport` intermediate model.

---

## Finding 7: Domain Expert Agents Missing output_schema (P2 — Quality)

**Location**: `agents/hephae_agents/research/pulse_domain_experts.py`

All three Stage 2 agents (PulseHistorySummarizer, EconomistAgent, LocalScoutAgent) use `output_key` but no `output_schema`. Their outputs are free-text strings written to session state. Adding structured output schemas would:
- Ensure consistent formatting for the synthesis stage
- Prevent LLM from including preamble/filler in the reports
- Enable validation

**Action**: Define lightweight Pydantic models for each expert's output (e.g., `MacroReport`, `LocalReport`, `TrendNarrative`) and set `output_schema` on each agent.

---

## Finding 8: ADK Callbacks Not Applied to Pulse Pipeline (P2 — Observability)

**Location**: `hephae_common/adk_helpers.py` has callback infrastructure, but pulse pipeline agents don't use `before_agent_callback` or `after_agent_callback`.

Adding callbacks would enable:
- Stage-level timing (how long does DataGatherer take vs Synthesis?)
- Token usage tracking per agent
- Automatic logging of state changes between stages

**Action**: Add timing/logging callbacks to `create_pulse_orchestrator()`. Can be as simple as:

```python
def log_agent_start(callback_context):
    logger.info(f"[Pulse] Starting {callback_context.agent_name}")

def log_agent_end(callback_context):
    logger.info(f"[Pulse] Completed {callback_context.agent_name}")
```

---

## Finding 9: No Tests (P1 — Coverage)

The implementation plan specified 21 tests across 7 categories. **Zero have been written.**

Priority test order:
1. **Schema validation** — `WeeklyPulseOutput` (and new `LocalBriefing`) handles nulls, validates scores
2. **Playbook matching** — `match_playbooks()` returns correct playbooks for given signals
3. **Impact multipliers** — `compute_impact_multipliers()` math is correct
4. **Cache-through** — `get_cached()` returns None on expiry, hit on valid
5. **Critique router** — escalate on pass, feedback on fail
6. **End-to-end** — generate pulse for test zip, validate output structure
7. **Batch processor** — JSONL generation, result parsing

**Action**: Create `tests/workflows/test_weekly_pulse.py` with at minimum tests 1-5 (unit-testable without API calls).

---

## Finding 10: Frontend Card for Local Briefing (P1 — Feature)

**Location**: `apps/admin/src/components/WeeklyPulse.tsx` (per local context plan)

The local context plan specifies a "This Week in [Town]" card rendered above insights in the admin UI. This card shows:
- Events with venue/date/impact
- Competitor watch notes
- Community buzz summary
- Government watch items

**Action**: Add `LocalBriefingCard` component that reads `pulse.localBriefing` and renders the four sections. Show above the insights list. Handle the case where `localBriefing` is null/undefined (older pulses without it).

---

## Implementation Order

| Priority | Finding | Effort | Dependencies |
|----------|---------|--------|-------------|
| 1 | F1: Signal archive bug | 30 min | None — debug + fix |
| 2 | F4a: LocalBriefing schema | 30 min | None |
| 3 | F4b: Synthesis prompt update | 1 hr | F4a |
| 4 | F4c: Combiner merge update | 1 hr | F4a |
| 5 | F5: Critique local quality pass | 1 hr | F4a |
| 6 | F6: LocalScout structured output | 30 min | F4a |
| 7 | F4d: Batch processor prompt | 30 min | F4a |
| 8 | F10: Frontend local briefing card | 1 hr | F4a |
| 9 | F2: Job timeout mechanism | 30 min | None |
| 10 | F3: DualModelSynthesis → LiteLlm | 2 hr | None (independent refactor) |
| 11 | F9: Tests | 2-3 hr | F4a, F5 |
| 12 | F7: Domain expert output_schema | 1 hr | None |
| 13 | F8: ADK callbacks | 30 min | None |

**Critical path**: F4a → F4b + F4c + F5 + F6 → F10 (local context feature end-to-end)
**Independent tracks**: F1 (bug fix), F2 (job timeout), F3 (ADK refactor), F9 (tests)

---

## Files to Modify

| File | Findings |
|------|----------|
| `lib/db/hephae_db/schemas/agent_outputs.py` | F4a: Add LocalEvent, CompetitorNote, LocalBriefing, update WeeklyPulseOutput |
| `agents/hephae_agents/research/weekly_pulse_agent.py` | F4b: Update WEEKLY_PULSE_CORE_INSTRUCTION for localBriefing |
| `agents/hephae_agents/research/pulse_orchestrator.py` | F3: Refactor DualModelSynthesis to LiteLlm; F4c: Update combiner |
| `agents/hephae_agents/research/pulse_critique_agent.py` | F5: Add Pass A local quality checks |
| `agents/hephae_agents/research/pulse_domain_experts.py` | F6: Update LocalScout instruction; F7: Add output_schema to all 3 |
| `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py` | F1: Debug signal archive; F8: Add callbacks |
| `apps/api/hephae_api/workflows/orchestrators/pulse_batch_processor.py` | F4d: Update batch prompt |
| `lib/db/hephae_db/firestore/pulse_jobs.py` | F2: Add timeoutAt field |
| `apps/api/hephae_api/routers/admin/weekly_pulse.py` | F2: Check timeout in status endpoint |
| `apps/admin/src/components/WeeklyPulse.tsx` | F10: Add LocalBriefingCard |
| `tests/workflows/test_weekly_pulse.py` | F9: New test file |

---

## Reference Documents

- Original implementation plan: `docs/weekly-pulse-implementation-plan.md`
- Local context gap plan: `docs/weekly-pulse-local-context-plan.md`
- ADK documentation: https://google.github.io/adk-docs/
- ADK LiteLlm multi-model: https://google.github.io/adk-docs/agents/models/
