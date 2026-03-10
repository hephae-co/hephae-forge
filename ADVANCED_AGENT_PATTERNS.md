# Advanced Agentic Patterns: Future Improvements

This document outlines high-level architectural improvements to transition the Hephae-Forge backend from a "Pipeline of Agents" to a "Robust Agentic OS."

---

## 1. The "Reflect" Pattern (Self-Correction)
*   **Current State:** Evaluation (e.g., `SeoEvaluatorAgent`) happens *after* the capability run. If it fails, the workflow simply notes the issue.
*   **Recommendation:** Wrap critical agents in an ADK `LoopAgent`.
*   **Workflow:** 
    1.  `SeoAuditor` runs.
    2.  `SeoEvaluator` (the Critic) checks the output.
    3.  If `isHallucinated` is `True` or `score < 70`, the `LoopAgent` triggers a **Retry** with the Critic's `issues` injected as a "correction hint."
*   **Benefit:** Dramatically reduces the need for manual admin intervention on "almost correct" runs.

---

## 2. Confidence-Score Metadata (Certainty API)
*   **Current State:** Every field (phone, email, logoUrl) is presented as a "Fact."
*   **Recommendation:** Update all agent Pydantic schemas to include a `confidence` metric (0.0 - 1.0) and a `source_reference` (URL/Snippet) for every field.
*   **UI Integration:** The frontend can then show "Unverified" badges or high-confidence checkmarks, helping users focus on data that needs manual review.

---

## 3. Agentic Search Loop (The "ReAct" Browser)
*   **Current State:** Agents like `SocialResearcher` or `CompetitiveAnalysis` do a single pass of Google Search and process the results.
*   **Recommendation:** Transition to a multi-turn **ReAct Loop**.
*   **Workflow:** 
    1. Agent searches for "Joe's Pizza".
    2. Agent identifies three potential URLs.
    3. Agent *decides* to crawl all three briefly to find the one with the matching address.
    4. Agent only proceeds with the "Confirmed" URL.
*   **Benefit:** Moves beyond "Extracting from Search Result Snippets" to "Verifying Facts on the Live Web."

---

## 4. Agentic Caching (Cost Optimization)
*   **Current State:** Large contexts (e.g., 30k chars of crawl data) are re-sent to every sub-agent in the `DiscoveryFanOut`.
*   **Recommendation:** Utilize ADK's `ContextCacheConfig` more aggressively.
*   **Action:** Cache the `rawSiteData` in Gemini's context cache. All 8 fan-out agents then point to the same cache ID.
*   **Benefit:** Reduces "Input Token" costs by up to 80% for the parallel stage of discovery.

---

## 5. Human-in-the-Loop (Interactive Handoffs)
*   **Current State:** The `WorkflowEngine` pauses for "Approval" but doesn't allow interactive "Correction."
*   **Recommendation:** Allow agents to emit a `ClarificationRequired` event.
*   **Example:** If Discovery finds three different phone numbers, the agent should be able to ask the user: *"I found three phones: A, B, and C. Which one is primary?"* rather than just picking one or failing.

---

## 6. Summary: Advanced Roadmap

| Pattern | Impact | Complexity | Priority |
| :--- | :--- | :--- | :--- |
| **Reflect (Self-Correction)** | High | Medium | **P1** |
| **Confidence Scoring** | High | Low | **P1** |
| **ReAct Search Loop** | Very High | High | **P2** |
| **Context Caching** | High (Cost) | Medium | **P1** |
| **Interactive Handoffs** | Medium | High | **P2** |
