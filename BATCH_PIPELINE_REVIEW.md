# Review: Autonomous Batch Pipeline & Human-in-the-Loop Design

This review outlines how to evolve the existing `discovery_jobs.py` logic into a professional, autonomous "Deep Sweep" pipeline that integrates seamlessly with your Admin UI for human approval.

---

## 1. Architectural Strategy: The "Staged Batch" Pattern
Instead of a single "Start-to-Finish" run, we treat the batch as a state machine that pauses at the "Approval Gate" in your Admin UI.

### New Proposed Job States:
1.  **`STATUS_RUNNING`**: Discovery & Analysis agents are active.
2.  **`STATUS_REVIEW_REQUIRED`**: (New) Agents have finished; the batch is waiting for an Admin to "Okay" businesses in the UI.
3.  **`STATUS_OUTREACH_PENDING`**: Admin has clicked "Approve," and the system is queuing outreach agents.
4.  **`STATUS_COMPLETED`**: Everything is done.

---

## 2. OpenClaw Pattern: The "Supervisor" Report
To make the Admin UI more impactful, we should use a **Supervisor Agent** at the end of the `RUNNING` phase.

### Recommendation: The "Batch Intelligence" Summary
*   **The Logic:** After 200 businesses are analyzed, a cheap Supervisor Agent (e.g., Gemini Flash) reads the scores and creates a summary for the Admin.
*   **Output in Admin UI:** 
    > *"Sweep of Zip Code 07042 complete. Found 142 businesses. **12 are High-Priority** (Profit leakage > $2k/mo). 5 look like duplicates. 3 have broken websites. Ready for your review."*
*   **Value:** The human doesn't have to hunt for the good leads; the Supervisor "surfaces" them.

---

## 3. Human-in-the-Loop Integration (Admin UI)

### P0 Action: Discovery Job "Approval" Metadata
Add these fields to each discovered business in Firestore (or to the `progress` object in the job):
*   **`adminApprovalStatus`**: `pending` | `approved` | `rejected`
*   **`evalReady`**: (Bool) If true, the data is verified and can be used for training/evaluating future agents.

### P1 Action: Feedback Loop (OpenClaw "Correction" Pattern)
When an admin rejects a business or corrects a data point (e.g., a phone number), we should save this as a **"Correction Event."**
*   **Future Use:** These events become the **Eval Dataset** used to automate the approval process later.

---

## 4. Implementation Roadmap: Gradual Automation

| Phase | Current (Manual Loop) | Target (Agentic Batch) | Priority |
| :--- | :--- | :--- | :--- |
| **Discovery** | Hardcoded logic | Municipal Hub + ADK Grounding | **P0** |
| **Reporting** | Individual rows | **Supervisor Summary Report** | **P1** |
| **Gate** | None (manual check) | **Explicit `REVIEW_REQUIRED` State** | **P0** |
| **Evaluation**| Manual export | **"Add to Evals" button in UI** | **P1** |

---

## 5. Summary Table: Why this is better

| Feature | Impact on Admin | Impact on Cost |
| :--- | :--- | :--- |
| **Batch States** | Clearer workflow; knows what to review. | No change. |
| **Supervisor Summary** | Saves ~30 mins of scrolling per zip code. | Negligible (1 cheap LLM call). |
| **Approval Gates** | Ensures high-quality outreach. | High (prevents wasted email credits). |
| **Correction Memory** | Improves future automation. | Strategic (Long-term Moat). |

**Would you like me to update the `discovery_jobs.py` schema and the `AreaResearchOrchestrator` to support these new "Review Required" states?**
