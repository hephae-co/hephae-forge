---
name: hephae-test-master
description: Specialized instructions for building, maintaining, and improving the Hephae Forge test suite. Use when creating new tests, fixing bugs, or expanding evaluation datasets to ensure high-fidelity verification and prevent regressions.
---

# Hephae Test Master: High-Fidelity Verification

This skill mandates a rigorous, tiered approach to testing to ensure that bugs and usability issues are caught early and never reach the user.

## 1. The Core Workflow: "Reproduction First"
**Mandate:** Every bug fix or feature implementation MUST start with a failing test case.

1. **Reproduction:** Identify the bug/gap and create a failing test in the appropriate tier.
2. **Strategy:** Plan the fix/change.
3. **Execution:** Implement the change.
4. **Validation:** Run the new test and the full suite to confirm success and prevent regressions.

---

## 2. Testing Tiers & Coverage

### Tier 1: Semantic Evals (ADK)
*   **Location:** `tests/evals/`
*   **Focus:** Individual agent quality and tone.
*   **Instruction:** Use **LLM-as-a-Judge** grading. Do not rely on `response_match_score` alone. Create a "Judge Agent" that evaluates the output against a specific semantic rubric (e.g., "Is the SEO advice actionable?").

### Tier 2: Ground Truth Integration
*   **Location:** `tests/integration/`
*   **Focus:** Real-world tool performance (Search, Crawl, Database).
*   **Instruction:** Assert against **Ground Truth** data in `tests/integration/businesses.py`. Verify actual accuracy (e.g., branding colors, social URLs, competitor names) rather than just checking if keys exist.

### Tier 3: E2E Lifecycle (Playwright)
*   **Location:** `apps/admin/src/tests/e2e/`
*   **Focus:** Full workflow state machine and UI state transitions.
*   **Instruction:** Test the **state transitions**. Verify that the UI correctly reflects the transition from `DISCOVERY` -> `ENRICHING` -> `ANALYZING` -> `ANALYSIS_DONE`.

---

## 3. Mandatory Testing Mandates

### A. Corner Case Testing
Add cases for:
- Broken or redirect-heavy URLs.
- Partial data (e.g., no website, only social presence).
- Rate-limited or bot-protected sites.
- Malformed or unconventional HTML.

### B. Business Logic Testing
Verify:
- **State Transitions:** Correct transitions in `WorkflowEngine`.
- **Scoring Formulas:** Accuracy of margin leakage and SEO scoring logic.
- **Capability Routing:** Ensuring only requested/relevant capabilities run for a business.

### C. Automated UI Coverage
Ensure:
- Approval/Reject workflows correctly update Firestore status.
- State-dependent components (e.g., Insights tab) only render when data is ready.
- Concurrent workflow runs do not bleed state in the UI.

### D. Session & Persistence Testing
Verify:
- `FirestoreSessionService` correctly persists state across agent restarts.
- Session IDs are correctly passed between Cloud Tasks and ADK.

### E. Continuous Eval Dataset Expansion
- **Strategy:** Every PR that improves an agent's prompt should add 1-2 new "Golden Fixture" cases to `eval.test.json`.
- **Diversity:** Include varied business categories (Restaurants, Retail, Services) and geographic locations.

---

## 4. Observability for Debugging
When a test fails:
1.  **Check Raw Thoughts:** Review the `thought` buffer in the agent's output.
2.  **Trace ID:** Use the `trace_id` or `session_id` to find the exact agent turn in the Firestore logs.
3.  **Semantic Post-Mortem:** Use an LLM to analyze the failing run's logs to identify if the issue is a tool failure or an LLM reasoning error.
