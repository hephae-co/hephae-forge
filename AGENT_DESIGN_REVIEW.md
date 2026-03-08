# Agentic Design Review: Hephae-Forge

## 1. Executive Summary
The backend successfully uses ADK for modular agents but currently "fights" the framework with manual Python orchestrators and brittle regex-based parsing. Transitioning to **Hierarchical Toolification** and **Native Structured Outputs** will unify UI/Batch modes and eliminate runtime parsing errors.

---

## 2. Priority 0: Critical (Immediate Impact)

### P0.1: Native Structured Output (The "Parsing Kill-Switch")
*   **Current Issue:** Widespread use of `run_agent_to_json` with manual `_strip_markdown_fences` and regex hacks (e.g., `_extract_dma_name` in `zipcode_research.py`).
*   **Mandate:** 
    1. Define Pydantic models for all agent outputs.
    2. Pass these models to `LlmAgent` using `response_schema` and `response_mime_type="application/json"`.
*   **Benefit:** Zero-parsing overhead. Guaranteed data integrity across agent handoffs.

### P0.2: Hierarchical Hub-and-Spoke Orchestration
*   **Current Issue:** Orchestrators like `AreaResearchOrchestrator` are hardcoded Python state machines, making them rigid for UI-driven exploration.
*   **Mandate:** 
    1. **"Toolify" Agents:** Wrap `DiscoveryPipeline` and `SeoAuditor` as `AgentTool` objects.
    2. **Coordinator Hub:** Implement a `BusinessOrchestrator` (CoordinatorAgent) for UI mode.
*   **UI Mode:** User asks a question -> Coordinator calls needed AgentTools.
*   **Batch Mode:** Directly invoke `DiscoveryPipeline` (Deterministic Chain).

---

## 3. Priority 1: Important (Reliability & Cost)

### P1.1: Persistent Firestore Session Service
*   **Current Issue:** `InMemorySessionService` forces manual "context injection" (e.g., `_with_all_discovery_data` in Discovery Stage 4).
*   **Mandate:** Implement a `FirestoreSessionService` to allow state to persist across workflow phases and UI turns.
*   **Benefit:** Native state access for agents; removes thousands of tokens of redundant "context re-injection" in prompts.

### P1.2: Native Grounding Tools
*   **Current Issue:** `google_search_tool` makes a recursive LLM call (agent-in-agent).
*   **Mandate:** Use ADK's native `google.adk.tools.google_search` where grounding is needed without reasoning.
*   **Benefit:** ~30% faster execution; 50% lower token cost per search.

---

## 4. Priority 2: Future-Proofing

### P2.1: Proactive "Heartbeat" Loop (OpenClaw)
*   **Action:** Implement a background worker that triggers a "Monitoring Agent" periodically for discovered businesses.
*   **Benefit:** Transitions the platform from a "Search Tool" to a proactive "Monitoring OS."

---

## 5. Summary Table

| Category | Task | Benefit |
| :--- | :--- | :--- |
| **P0** | **Structured JSON Schema** | Eliminates 100% of regex/parsing bugs. |
| **P0** | **AgentTool Wrapping** | Unifies UI (Agentic) & Batch (Deterministic) modes. |
| **P1** | **Firestore Session** | Native memory; reduces context-window bloat. |
| **P1** | **Direct Grounding** | Removes redundant "agent-inside-agent" hops. |
| **P2** | **Heartbeat Agent** | Proactive vs Reactive intelligence. |
