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

### Check 2: Session State Management

For agents using session state (`ctx.session.state`):

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| State keys | Should be documented / consistent across agents | Look for magic strings |
| State delta | Should use `EventActions(state_delta=...)` not direct mutation | Check for `state["key"] = value` |
| State size | Large data should be summarized, not dumped into state | Check for state values > 10KB |

### Check 3: Agent Orchestration

For SequentialAgent / ParallelAgent / LoopAgent:

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| ParallelAgent | Independent sub-tasks should run in parallel | Are there sequential agents that could be parallel? |
| LoopAgent | Should have max_iterations set | Check for unbounded loops |
| Sub-agent naming | Names should be descriptive and unique | Check for generic names |
| Agent tree depth | Max 3 levels recommended | Check nesting depth |

### Check 4: Tool Design

For each tool definition:

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| Return type | Tools should return structured data, not raw strings | Check return types |
| Error handling | Tools should handle errors gracefully (return error dict, not raise) | Check for bare raises |
| Docstrings | Every tool needs a clear docstring (LLM reads it) | Check for missing docstrings |
| Async | I/O-bound tools should be async | Check for sync HTTP calls in tools |
| Side effects | Tools should be idempotent where possible | Flag tools that write to DB |

### Check 5: Model Usage Patterns

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| Thinking mode | MEDIUM for evals, HIGH for analysis, DEEP for complex synthesis | Check thinking level matches task complexity |
| Fallback chain | Primary → Fallback on 429/503/529 | Verify fallback is configured |
| Batch API | Multiple independent LLM calls should use batch_generate() | Check for sequential LLM calls that could be batched |
| Context window | Don't stuff 100K tokens into a prompt | Estimate prompt size for each agent |
| Temperature | Should be default (not explicitly set) for most agents | Check for temperature overrides |

### Check 6: Structured Output

| Pattern | Best Practice | What to Check |
|---------|--------------|---------------|
| JSON output | Use `output_schema=PydanticModel` instead of asking LLM to "return JSON" | Check for "Return JSON" / "Return ONLY valid JSON" in instructions |
| Response parsing | Use ADK native parsing, not manual json.loads() | Check for manual JSON extraction |
| Schema validation | Output should be validated against a Pydantic model | Check for raw dict returns |

### Check 7: Gemini-Specific Features

| Feature | Best Practice | What to Check |
|---------|--------------|---------------|
| Google Search grounding | Use `google_search` tool from `google.adk.tools` | Check if any agent does manual web scraping when grounding would work |
| Code execution | Use code_execution tool for math/data processing | Check if agents do calculations that could be offloaded |
| Function calling | Use native function calling, not prompt-based tool selection | Check for "call the {tool_name} tool" in prompts |

---

## PHASE 3: FINDINGS

For each issue found:

```markdown
### FINDING-{N}: {title} [{CRITICAL|HIGH|MEDIUM|LOW}]
- **File:** `{path}:{line}`
- **Pattern:** {which check failed}
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
- `from google.adk.tools import google_search, FunctionTool`
- `from google.adk.events import Event, EventActions`
- `from google.adk.agents.invocation_context import InvocationContext`

## What NOT To Do

- Do NOT modify any code. Read-only audit.
- Do NOT flag patterns that work correctly — focus on actual issues.
- Do NOT recommend architectural rewrites — suggest incremental improvements.
- Do NOT flag deprecated APIs without checking if they still work in the current version.
