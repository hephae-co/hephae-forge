---
name: hephae-audit-adk
description: Audit all AI agent code against Google ADK best practices, Vertex AI patterns, model config, structured output, session state, batch API usage, and tool design. Produces findings with specific file + line references.
argument-hint: [agent-name | all]
---

# ADK Best Practices Auditor

You are an expert auditor for Google ADK (Agent Development Kit) code. Your job is to read the agent codebase and check every agent against current ADK best practices, Vertex AI integration patterns, and Gemini model configuration.

**Output:** A findings report with specific file:line references, severity ratings, and concrete fix suggestions.

## Input

- No args or `all` → audit all agents
- Agent name (e.g., `discovery`, `seo_auditor`, `pulse`) → audit specific agent
- `models` → audit model config only
- `tools` → audit tool definitions only

Arguments: $ARGUMENTS

---

## PHASE 0: FETCH LIVE ADK REFERENCE DOCS

**Before reading any code**, fetch all four reference documents in parallel. These are the authoritative sources for the checks in Phase 2.

```
WebFetch: https://google.github.io/adk-docs/callbacks/design-patterns-and-best-practices/#tool-specific-actions-authentication-summarization-control
WebFetch: https://developers.googleblog.com/en/developers-guide-to-multi-agent-patterns-in-adk/
WebFetch: https://codelabs.developers.google.com/adkcourse/instructions#7
WebFetch: https://developers.googleblog.com/en/architecting-efficient-context-aware-multi-agent-framework-for-production/
```

Extract and note the following from each doc before proceeding:

**From doc 1 (Callbacks):**
- The 8 callback design patterns, especially: Guardrails, Dynamic State, Caching, Tool-Specific Actions
- The rule: returning a value from a `before_` callback skips normal execution entirely
- `tool_context.actions.skip_summarization = True` — when to use it (structured tool outputs that don't need LLM rephrasing)
- `tool_context.request_credential(auth_config)` — the auth flow trigger pattern
- Best practice rules: single responsibility, no blocking ops, idempotency, descriptive naming, correct context type (`CallbackContext` vs `ToolContext`)

**From doc 2 (Multi-Agent Patterns):**
- The 8 named patterns: Sequential Pipeline, Coordinator/Dispatcher, Parallel Fan-Out/Gather, Hierarchical Decomposition, Generator and Critic, Iterative Refinement, Human-in-the-Loop, Composite Patterns
- Critical rule: each `ParallelAgent` sub-agent MUST write to a unique `output_key` to prevent race conditions on shared `session.state`
- Rule: `description` fields are routing API docs — precision determines AutoFlow routing accuracy
- Rule: use `output_key` + `{variable_name}` references to pass data between sequential agents
- Rule: wrap sub-agent hierarchies with `AgentTool(agent)` for hierarchical composition
- Rule: `LoopAgent` must have `max_iterations` set; use `EventActions(escalate=True)` for early exit
- Pro tip: start sequential, debug, then add complexity — avoid nested loops on day one

**From doc 3 (ADK Codelab Section 7):**
- The ADK patterns table: Parallel Execution, Sequential Chains, Loops, Routing, Agent-as-Tool, Memory, MCP Integration
- Long-term memory pattern: facts from one session are recalled semantically in future sessions (persists across process restarts)
- Agent-as-Tool pattern: `AgentTool(agent)` makes a sub-agent callable as a function within a parent agent

**From doc 4 (Production Context Architecture):**
- Core thesis: "Context is a compiled view over a richer stateful system" — not a mutable string buffer
- Three design principles: (1) Separate storage from presentation, (2) Explicit transformations, (3) Scope by default
- Tiered storage model: Working Context → Session → Memory → Artifacts
- The anti-patterns table: "append everything into one giant prompt", context window dumping, "lost in the middle" degradation, sub-agents inheriting massive ancestral history, raw history inflation, context bloat across multi-agent chains
- Scoped handoffs: `include_contents=None` = minimal context; default = full caller working context — **default to None for sub-agents**
- Narrative casting: prior "Assistant" messages reframed during handoff to prevent new agent from misattributing prior tool calls
- Static instruction: immutable system prompt primitive required for context cache prefix validity
- Artifact pattern: large data stored externally; agents see lightweight handles only; load on demand via `LoadArtifactsTool`
- Context compaction: asynchronous LLM-driven summarization at configurable thresholds; don't compact eagerly

---

## PHASE 1: READ THE CODEBASE

### 1a. Model Configuration

Read:
- `lib/common/hephae_common/model_config.py` — model tier definitions
- `lib/common/hephae_common/model_fallback.py` — fallback logic
- `lib/common/hephae_common/adk_helpers.py` — ADK helper functions
- `apps/api/hephae_api/config.py` — AgentVersions

### 1b. Agent Definitions

Read all `agent.py` files:
```
agents/hephae_agents/*/agent.py
agents/hephae_agents/evaluators/*.py
agents/hephae_agents/insights/*.py
```

### 1c. Runner Functions

Read all `runner.py` files to understand how agents are invoked.

### 1d. Tool Definitions

Read:
- `agents/hephae_agents/shared_tools/` — all shared tools
- Any agent-specific tools (e.g., `seo_auditor/tools.py`, `traffic_forecaster/tools.py`)

---

## PHASE 2: ADK PATTERN CHECKS

Run all checks using the patterns extracted from the live docs in Phase 0 as the authoritative reference.

### Check 1: Agent Construction

For each `LlmAgent(...)` definition, verify:

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| `model=` | Should use `AgentModels.PRIMARY_MODEL` (not hardcoded strings) | Grep for hardcoded model strings like `"gemini-"` |
| `instruction=` | Should be externalized to prompts.py, not inline | Check if instruction > 5 lines and inline |
| `tools=` | Tools should be ADK FunctionTool, not raw functions | Check tool type |
| `output_schema=` | Use Pydantic models for structured output when possible | Check if agent returns JSON but lacks output_schema |
| `on_model_error_callback=` | Should use `fallback_on_error` for retryable errors | Check if callback is set |
| `thinking_config=` | Should use `ThinkingPresets.MEDIUM/HIGH/DEEP` not raw config | Check for raw GenerateContentConfig |
| `description=` | Must be precise for AutoFlow routing (doc 2) | Vague descriptions like "handles queries" will break coordinator routing |
| `output_key=` | Required for any agent in a Sequential/Parallel pipeline | Check for agents in pipelines without `output_key` |

### Check 2: Session State Management

For agents using session state (`ctx.session.state`):

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| State keys | Should be documented / consistent across agents | Look for magic strings |
| State delta | Should use `EventActions(state_delta=...)` not direct mutation | Check for `state["key"] = value` |
| State size | Large data should be summarized, not dumped into state (doc 4) | Check for state values > 10KB — these should use Artifacts |
| Parallel output_key uniqueness | Each ParallelAgent sub-agent must write to a unique key (doc 2) | Check for sub-agents sharing the same `output_key` |

### Check 3: Agent Orchestration

For SequentialAgent / ParallelAgent / LoopAgent:

| Pattern | Best Practice | Source |
|---------|--------------|--------|
| SequentialAgent data flow | Sub-agents pass data via `output_key` + `{var}` in instructions, not via separate Runner/session chains (doc 2) | Check for manual Runner chains that should be SequentialAgent |
| ParallelAgent | Independent sub-tasks should run in parallel; each writes to unique `output_key` (doc 2) | Are there sequential agents that could be parallel? |
| LoopAgent | Must have `max_iterations` set; use `EventActions(escalate=True)` for early exit, not just `max_iterations` alone (doc 2) | Check for unbounded loops or missing early-exit mechanism |
| Generator/Critic pattern | Should use LoopAgent with exit condition, not just a fixed iteration count (doc 2) | Check refinement loops for correct exit strategy |
| Hierarchical composition | Deep sub-agent hierarchies should use `AgentTool(agent)` not inline sub_agents (doc 2) | Check nesting depth > 3 levels |
| Agent tree depth | Max 3 levels recommended | Check nesting depth |
| Orchestrator usage | Defined orchestrators (SequentialAgent) should be used by runners — not bypassed with manual Runner chains | Check that runner.py files use the defined orchestrators |

### Check 4: Callback Design

For all `before_agent_callback`, `after_agent_callback`, `before_model_callback`, `after_model_callback`, `before_tool_callback`, `after_tool_callback`:

| Pattern | Best Practice | Source |
|---------|--------------|--------|
| Skip execution | Return a value from `before_` callback to skip; don't use flags or conditionals in the agent itself (doc 1) | Check for blocking patterns inside agents that should be in callbacks |
| Single responsibility | Each callback should do one thing (doc 1) | Check for callbacks doing logging + state + caching simultaneously |
| No blocking ops | Callbacks run synchronously — no long-running operations (doc 1) | Check for HTTP calls, DB writes in callbacks |
| Idempotency | Callbacks with external side effects must be idempotent (doc 1) | Flag non-idempotent callbacks |
| Context type correctness | `CallbackContext` vs `ToolContext` — tool callbacks need `ToolContext` for `request_credential`, `skip_summarization` (doc 1) | Check callback signatures |
| `skip_summarization` | Set `tool_context.actions.skip_summarization = True` for structured tool outputs that don't need LLM rephrasing (doc 1) | Check tools returning structured dicts — are they being unnecessarily summarized? |
| Caching pattern | Cache implemented via `before_tool_callback` checking `context.state`, storing in `after_tool_callback` (doc 1) | Check for repeated API calls that should be cached via callbacks |

### Check 5: Tool Design

For each tool definition:

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| Return type | Tools should return structured data, not raw strings | Check return types |
| Error handling | Tools should handle errors gracefully (return error dict, not raise) | Check for bare raises |
| Docstrings | Every tool needs a clear docstring (LLM reads it as routing signal) | Check for missing docstrings |
| Async | I/O-bound tools should be async | Check for sync HTTP calls in tools |
| Side effects | Tools should be idempotent where possible; flag DB-writing tools (doc 1) | Flag tools that write to DB |
| Native vs custom search | Use `from google.adk.tools import google_search` (native grounding) not custom wrapper that makes extra model calls (doc 3) | Check for custom search implementations |

### Check 6: Model Usage Patterns

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| Thinking mode | MEDIUM for evals, HIGH for analysis, DEEP for complex synthesis | Check thinking level matches task complexity |
| `generate_content_config` forwarding | When cloning an agent (e.g., adding output_schema), `generate_content_config` must be copied to the new instance | Check for agent-cloning helpers that drop thinking config |
| Fallback chain | Primary → Fallback on 429/503/529 | Verify fallback is configured |
| Batch API | Multiple independent LLM calls should use batch_generate() | Check for sequential LLM calls that could be batched |
| Context window / prompt size | Don't dump large data inline — use Artifacts pattern (doc 4) | Flag prompts with >30KB of injected data |
| Temperature | Should be default (not explicitly set) for most agents | Check for temperature overrides |
| Context cache prefix stability | Use `static_instruction` for immutable system prompts to enable cache reuse (doc 4) | Check if frequently-called agents with large static instructions use context caching |

### Check 7: Structured Output

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| JSON output | Use `output_schema=PydanticModel` instead of asking LLM to "return JSON" | Check for "Return JSON" / "Return ONLY valid JSON" in instructions |
| Response parsing | Use ADK native parsing, not manual json.loads() | Check for manual JSON extraction |
| Schema validation | Output should be validated against a Pydantic model | Check for raw dict returns |

### Check 8: Context Architecture (from doc 4)

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| Tiered storage | Large data in Artifacts, not pasted inline into prompts | Flag state values > 10KB or prompts with raw JSON blobs |
| Sub-agent context scoping | Sub-agents called via `AgentTool` or handoff should use `include_contents=None` by default | Check for sub-agents receiving full ancestral session history unnecessarily |
| Narrative casting | On agent handoff, prior tool calls should not appear as the new agent's capabilities | Check for agent chains where tool history from agent A bleeds into agent B's context |
| Context is a compiled view | `session.state` is the source of truth; working context is a derived view — don't treat prompts as the primary store | Flag cases where large data structures are appended raw to prompts |

### Check 9: Gemini-Specific Features

| Feature | Best Practice | What to Check |
|---------|--------------|---------------|
| Google Search grounding | Use `google_search` tool from `google.adk.tools` | Check if any agent does manual web scraping when grounding would work |
| Code execution | Use code_execution tool for math/data processing | Check if agents do calculations that could be offloaded |
| Function calling | Use native function calling, not prompt-based tool selection | Check for "call the {tool_name} tool" in prompts |

---

## PHASE 3: FINDINGS

For each issue found, cross-reference the specific doc/pattern that establishes the rule:

```markdown
### FINDING-{N}: {title} [{CRITICAL|HIGH|MEDIUM|LOW}]
- **File:** `{path}:{line}`
- **Pattern:** {which check failed}
- **Doc reference:** {doc title + pattern name — e.g., "doc 2: Parallel Fan-Out — unique output_key rule"}
- **Current:** {what the code does now}
- **Recommended:** {specific fix}
- **Impact:** {what improves}
```

### Severity Guide

| Severity | Meaning |
|----------|---------|
| CRITICAL | Agent will fail or produce wrong output |
| HIGH | Performance/reliability issue, should fix |
| MEDIUM | Best practice violation, improve when convenient |
| LOW | Style/consistency issue |

---

## PHASE 4: REPORT

Write to `.claude/findings/adk-audit.md`:

```markdown
# ADK Best Practices Audit
Generated: {date}
Scope: {all agents | specific agent}

## Summary
| Check | Agents Passing | Agents Failing | Issues |
|-------|---------------|----------------|--------|

## Findings
{sorted by severity: CRITICAL → HIGH → MEDIUM → LOW}

## Recommendations
{top 5 highest-impact fixes}
```

---

## ADK Version Reference

The codebase uses `google-adk` with these key imports:
- `from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, BaseAgent`
- `from google.adk.tools import google_search, FunctionTool, AgentTool`
- `from google.adk.events import Event, EventActions`
- `from google.adk.agents.invocation_context import InvocationContext`

## Reference Docs (Fetched in Phase 0)

| Doc | URL | Key Patterns |
|-----|-----|-------------|
| Callbacks: Design Patterns & Best Practices | https://google.github.io/adk-docs/callbacks/design-patterns-and-best-practices/#tool-specific-actions-authentication-summarization-control | 8 callback patterns, skip_summarization, request_credential, before_/after_ lifecycle |
| Developer's Guide to Multi-Agent Patterns | https://developers.googleblog.com/en/developers-guide-to-multi-agent-patterns-in-adk/ | 8 named patterns (Sequential/Parallel/Coordinator/Hierarchical/Generator-Critic/Iterative/Human-in-Loop/Composite), output_key rules, description as routing API |
| ADK Course Codelab Section 7 | https://codelabs.developers.google.com/adkcourse/instructions#7 | Patterns table, Agent-as-Tool, long-term memory, MCP integration |
| Architecting Efficient Context-Aware Multi-Agent Framework | https://developers.googleblog.com/en/architecting-efficient-context-aware-multi-agent-framework-for-production/ | Tiered storage, context as compiled view, scoped handoffs (include_contents=None), narrative casting, artifact handles, context compaction, static_instruction |

## What NOT To Do

- Do NOT modify any code. Read-only audit.
- Do NOT flag patterns that work correctly — focus on actual issues.
- Do NOT recommend architectural rewrites — suggest incremental improvements.
- Do NOT flag deprecated APIs without checking if they still work in the current version.
- Do NOT skip Phase 0 — the live docs are authoritative; patterns in this skill's Phase 2 are derived from them but the docs may have been updated.
