# ADK Best Practices Audit
Generated: 2026-03-22
Scope: All agents

---

## Summary

| Check | Passing | Failing | Issues |
|-------|---------|---------|--------|
| Model construction (model=, fallback, thinking) | 12 | 2 | Hardcoded temperature; thinking config silently dropped |
| Session state management | ✓ | — | Clean EventActions usage throughout |
| Agent orchestration (Sequential/Parallel/Loop) | 2 | 2 | Marketing swarm and Margin runner bypass their orchestrators |
| Tool design (docstrings, async, error handling) | ✓ | 1 | Mock data in benchmark tool |
| Model usage patterns (thinking, batch) | 5 | 1 | Temperature override in Forecaster |
| Structured output (JSON mode, schema) | 3 | 2 | "Return ONLY valid JSON" flood; schema cloning drops thinking config |
| Gemini-specific (native search, code execution) | partial | 1 | Custom google_search wrapper used alongside native tool |
| Import / dependency graph | 5 | 5 | 5 agent files import from `hephae_api.config` — violates CLAUDE.md |

---

## Findings

---

### FINDING-1: `run_agent_to_json` silently drops `generate_content_config` [CRITICAL]
- **File:** `lib/common/hephae_common/adk_helpers.py:137-146`
- **Pattern:** Agent construction — `generate_content_config` stripped on schema wrap
- **Current:** `run_agent_to_json` creates a `schema_agent = LlmAgent(...)` copy that does not forward `generate_content_config` from the source agent. Any agent defined with `ThinkingPresets.DEEP` or `ThinkingPresets.HIGH` that is invoked via `run_agent_to_json` silently loses its thinking budget.
- **Affected agents:**
  - `AreaSummaryAgent` — defined with `ThinkingPresets.DEEP`, called via `run_agent_to_json` (`area_summary.py:95`)
  - `EnhancedAreaSummaryAgent` — same (`area_summary.py:142`)
  - `InsightsAgent` — no thinking set (acceptable), but any future DEEP agent called this way will silently degrade
- **Recommended:** Forward `generate_content_config` in the schema clone:
  ```python
  schema_agent = LlmAgent(
      ...
      generate_content_config=agent.generate_content_config,  # ADD THIS
      output_schema=response_schema,
  )
  ```
- **Impact:** Area summary and enhanced area summary agents run without thinking — outputs for complex multi-zip synthesis use a simpler reasoning path than intended.

---

### FINDING-2: Agents import `AgentModels` from `hephae_api.config` — dependency violation [HIGH]
- **Files:**
  - `agents/hephae_agents/research/pulse_orchestrator.py:31`
  - `agents/hephae_agents/research/intel_fan_out.py:26`
  - `agents/hephae_agents/evaluators/seo_evaluator.py:7`
  - `agents/hephae_agents/evaluators/traffic_evaluator.py:7`
  - `agents/hephae_agents/insights/insights_agent.py:15`
  - `agents/hephae_agents/research/area_summary.py:10`
- **Pattern:** Import / dependency graph
- **Current:** These files do `from hephae_api.config import AgentModels, ThinkingPresets`. The CLAUDE.md dependency graph explicitly states `hephae-agents → hephae-common` only — not `hephae-agents → hephae-api`. Since `hephae-api` imports from `hephae-agents`, this creates a circular dependency that could cause import errors on standalone agent usage, test isolation failures, and breaks the stated contract.
- **Recommended:** Change all affected imports to:
  ```python
  from hephae_common.model_config import AgentModels, ThinkingPresets
  ```
  (The identical symbols are already defined there — this is a straight substitution.)
- **Impact:** Agent package cannot be used without importing the full API layer. Breaks test isolation and standalone runner usage.

---

### FINDING-3: Marketing swarm manually chains 3 Runners instead of SequentialAgent [HIGH]
- **File:** `agents/hephae_agents/social/marketing_swarm/agent.py:125-199`
- **Pattern:** Agent orchestration — sequential pipeline re-implemented manually
- **Current:** `run_marketing_pipeline` creates 3 separate Runner instances (one per agent: CreativeDirector, PlatformRouter, Copywriter), each with its own session, and passes output from one to the next via string interpolation in `user_msg()`. The actual agent definitions at the top of the file are `LlmAgent` objects that are correctly defined, but they're never wired into an ADK orchestrator — the coordination logic is all bespoke Python.
- **Recommended:** Implement using `SequentialAgent` with dynamic instructions reading from session state (same pattern as `competitive_analysis/agent.py`). Each agent writes to `output_key`, the next reads from `ctx.state`. The 3 separate Runner/session setups collapse into one.
- **Impact:** No shared state between agents (each gets a fresh session), output is passed as string injection into prompts which is fragile. Maintenance burden: any change to the pipeline requires updating the manual wiring. The defined agents at module top are effectively decorative.

---

### FINDING-4: Margin runner bypasses `margin_surgery_orchestrator` SequentialAgent [HIGH]
- **File:** `agents/hephae_agents/margin_analyzer/runner.py:110-270`
- **Pattern:** Agent orchestration — orchestrator defined but not used
- **Current:** `margin_analyzer/agent.py` correctly defines `margin_surgery_orchestrator` as a `SequentialAgent` with `benchmark_and_commodity` as a `ParallelAgent` sub-step. But `runner.py` completely ignores this orchestrator and manually creates individual Runner instances for each agent step, with manual `asyncio.gather` for the parallel step. The orchestrator is dead code.
- **Recommended:** Replace the manual Runner chain with a single `Runner(agent=margin_surgery_orchestrator)` invocation. The `SequentialAgent` handles stage sequencing, the `ParallelAgent` handles benchmarker/commodity parallelism. Remove the manual per-step Runner setup.
- **Impact:** Duplicate coordination logic, the ParallelAgent is not used (benchmarker and commodity_watchdog run via asyncio.gather instead of ADK-managed parallelism), session state is not shared naturally between steps, and callbacks (`log_agent_start`, `log_agent_complete`) on the orchestrator never fire.

---

### FINDING-5: Traffic Forecaster synthesis bypasses ADK with `temperature=0.2` [HIGH]
- **File:** `agents/hephae_agents/traffic_forecaster/agent.py:258-268`
- **Pattern:** Model usage — temperature override + ADK bypass
- **Current:** The synthesis step calls `generate_with_fallback(...)` directly (not via ADK Runner), with `temperature=0.2` explicitly set. Temperature overrides should be avoided per CLAUDE.md standards ("Should be default (not explicitly set) for most agents"). The synthesis also includes `"Return ONLY valid JSON matching this structure perfectly"` (line 228) while simultaneously setting `response_schema=TrafficForecastOutput` — both are set, which is redundant and potentially conflicting.
- **Recommended:**
  1. Remove `temperature=0.2` — let Gemini use its default.
  2. Remove the "Return ONLY valid JSON" instruction from the prompt — `response_schema` already constrains output.
  3. Consider wrapping the synthesis in an `LlmAgent` with `output_schema=TrafficForecastOutput` to bring it into the ADK session lifecycle.
- **Impact:** Non-default temperature can produce overconfident or repetitive JSON outputs. The parallel instruction + schema setup can cause schema violations when the model tries to satisfy both simultaneously.

---

### FINDING-6: Widespread "Return ONLY valid JSON" instruction in agents using native JSON mode [MEDIUM]
- **Files (15 occurrences):**
  - `qualification/scanner.py:351, 473`
  - `traffic_forecaster/agent.py:228`
  - `research/area_summary.py:57, 82`
  - `business_overview/agent.py:28, 41, 104`
  - `research/context_combiner.py:32`
  - `research/local_sector_trends.py:34`
  - `research/industry_news.py:37`
  - `research/industry_analyst.py:40`
  - `research/zipcode_report_composer.py:45`
  - `insights/insights_agent.py:39`
  - `research/tech_scout.py:147`
  - `research/maps_grounding.py:45`
  - `research/demographic_expert.py:44`
- **Pattern:** Structured output — redundant JSON instruction when native JSON mode active
- **Current:** Agents called via `run_agent_to_json` already have `response_mime_type: "application/json"` enforced. Agents with `output_schema=` have Gemini's schema-constrained output active. The explicit "Return ONLY valid JSON" instructions are redundant in both cases.
- **Recommended:** Remove these instructions from agents that always use `output_schema` or `run_agent_to_json`. Keep only in agents that may be called in text mode (e.g. `seo_auditor` which outputs prose).
- **Impact:** When both a schema constraint and a JSON instruction coexist, the model can get confused about which format to prioritize, leading to escaped JSON or schema violations. Removing the redundant instruction reduces prompt token count and ambiguity.

---

### FINDING-7: Custom `google_search_tool` used inconsistently alongside native `google_search` [MEDIUM]
- **File:** `agents/hephae_agents/shared_tools/google_search.py` vs `pulse_orchestrator.py:29, intel_fan_out.py:107`
- **Pattern:** Gemini-specific features — native grounding tool not used consistently
- **Current:** Two different search tools exist:
  1. `from google.adk.tools import google_search` — ADK's native Gemini grounding tool (no extra API call)
  2. Custom `google_search_tool` in `shared_tools/google_search.py` — makes a separate `generate_content_with_grounding` call and returns the result as a dict via a FunctionTool

  `pulse_orchestrator.py` (line 242) uses the native ADK `google_search` for `SocialPulseResearch`. `intel_fan_out.py` (line 107) uses the custom `google_search_tool` for `IndustryNewsIntel`. Most discovery agents use the custom wrapper. Some pulse agents use the native tool.
- **Recommended:** Standardize on the native `from google.adk.tools import google_search` wherever agents don't need the URL/sources dict returned from search. The native tool is simpler, uses fewer tokens, and doesn't make an extra model call. Reserve the custom wrapper only for agents that need structured `{result, sources}` output for downstream processing.
- **Impact:** Agents using the custom wrapper consume 2x the tokens per search (one to run the grounded search, one to format the result). At scale across 9 discovery agents, this adds significant cost.

---

### FINDING-8: LiteLlm model string hardcoded outside AgentModels [MEDIUM]
- **File:** `agents/hephae_agents/research/pulse_orchestrator.py:305`
- **Pattern:** Model construction — model string not in central config
- **Current:** `LiteLlm(model="anthropic/claude-sonnet-4-20250514")` is a hardcoded string. If this Claude model is deprecated or upgraded, it must be found and updated manually. There's no entry in `AgentModels` for the Claude model.
- **Recommended:** Add to `model_config.py`:
  ```python
  CLAUDE_SYNTHESIS_MODEL = "anthropic/claude-sonnet-4-20250514"
  ```
  Then use `AgentModels.CLAUDE_SYNTHESIS_MODEL` in the orchestrator.
- **Impact:** Model upgrades require grep-and-replace rather than a single config change.

---

### FINDING-9: `_gate_agent` mutates `LlmAgent.instruction` at module load time [MEDIUM]
- **File:** `agents/hephae_agents/discovery/agent.py:329-377`
- **Pattern:** Session state / agent construction — mutable shared agent object
- **Current:** `_gate_agent(contact_agent, _should_skip_contact, "contactData")` does `agent.instruction = _gated_instruction` — directly mutating the instruction attribute of the shared `contact_agent` LlmAgent object. If this module is imported multiple times in a process, or if the same agent object is used in a different pipeline later, the gated instruction permanently replaces the original.
- **Recommended:** Instead of mutating the agent, create a new `LlmAgent` with the gated instruction:
  ```python
  gated_contact_agent = LlmAgent(
      **{**vars(contact_agent), "instruction": _gated_instruction}
  )
  ```
  Or use `before_agent_callback` to implement skipping via `EventActions(skip_llm_response=True)` which is the ADK-native skip mechanism.
- **Impact:** Module-level agent mutation is fragile and can cause subtle bugs when agents are shared across pipelines. The discovery pipeline already uses a factory pattern for pulse (via `create_pulse_orchestrator()`); discovery should follow suit.

---

### FINDING-10: `_run_agent_with_schema` in adk_helpers.py is dead code [LOW]
- **File:** `lib/common/hephae_common/adk_helpers.py:183-244`
- **Pattern:** Code cleanliness — unused function
- **Current:** `_run_agent_with_schema` (private) is never called from any runner or agent file. `run_agent_to_json` is the public equivalent that's actually used. The private function is 60 lines of duplicate logic that will drift from the public version.
- **Recommended:** Remove `_run_agent_with_schema`. If native schema pinning without JSON mode is needed in the future, it can be re-added.
- **Impact:** Dead code that will confuse future maintainers and may be accidentally called.

---

### FINDING-11: `fetch_competitor_benchmarks` uses random mock pricing [LOW]
- **File:** `agents/hephae_agents/margin_analyzer/tools.py:49-58`
- **Pattern:** Tool design — stub data without clear documentation
- **Current:** `random.uniform(-1, 3)` generates fake competitor prices for each menu item. The `import random` at line 46 inside the function body is a code smell, and the resulting `competitors` list contains fabricated prices attributed to "Competitor near {location}". The BenchmarkerAgent presents these as real data to the SurgeonAgent.
- **Recommended:** Add a prominent docstring warning: `# STUB — returns mock pricing. Replace with real competitor pricing API (e.g., Yelp, Google Places).` Also consider returning an empty list or a clearly labeled `{"stub": true}` flag so downstream agents can handle the absence of real data gracefully rather than reasoning over random numbers.
- **Impact:** The SurgeonAgent makes pricing recommendations based on fabricated competitor prices. The advice may be directionally wrong if the random price happens to be far from reality.

---

## Recommendations (Top 5 by Impact)

### 1. Fix `run_agent_to_json` to forward `generate_content_config` [CRITICAL]
**File:** `lib/common/hephae_common/adk_helpers.py:137-146`
One line fix — add `generate_content_config=agent.generate_content_config` to the `schema_agent` constructor. Immediately restores thinking budgets for AreaSummaryAgent and EnhancedAreaSummaryAgent which currently run without any thinking enabled.

### 2. Fix circular dependency — change 6 files to import from `hephae_common` [HIGH]
**Files:** `pulse_orchestrator.py`, `intel_fan_out.py`, `seo_evaluator.py`, `traffic_evaluator.py`, `insights_agent.py`, `area_summary.py`
Change `from hephae_api.config import AgentModels, ThinkingPresets` to `from hephae_common.model_config import AgentModels, ThinkingPresets`. Zero behavior change, fixes the dependency graph stated in CLAUDE.md.

### 3. Wire `margin_surgery_orchestrator` into the runner [HIGH]
**File:** `agents/hephae_agents/margin_analyzer/runner.py`
Replace the ~160-line manual runner chain with a single `Runner(agent=margin_surgery_orchestrator)` call. The orchestrator and parallel sub-agent are already correctly defined in `agent.py` — the runner just ignores them. This collapses 5 separate Runner/session constructions and makes the `before_agent_callback` logging fire correctly.

### 4. Refactor marketing swarm to use SequentialAgent [HIGH]
**File:** `agents/hephae_agents/social/marketing_swarm/agent.py`
Convert `run_marketing_pipeline` to use an ADK SequentialAgent (following `competitive_analysis/agent.py` as the reference pattern). Each of the 3 agents already uses `output_key`, so state flow will work natively. This eliminates 3 separate sessions and the string-passing approach.

### 5. Standardize on native `google_search` tool [MEDIUM]
Replace the custom `google_search_tool` wrapper with `from google.adk.tools import google_search` across all discovery and research agents. The custom wrapper doubles the token cost of every search. Update `shared_tools/__init__.py` to export `google_search_tool = google_search` as an alias for a clean migration.
