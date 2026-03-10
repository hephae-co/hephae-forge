# Implementation Plan: Scaling UI Actions via Task Dispatcher

This plan outlines how to "Hook into" your existing Admin UI (Bulk Toolbar) to support large-scale, reliable agentic execution using Google Cloud Tasks and a Unified Task Ledger.

---

## 1. The Strategy: "From Click to Queue"
Currently, clicking "Analyze All" in the UI sends a bulk request that the backend processes in-process. This will time out or hit rate limits if you select 50+ businesses.

### The Change:
When you click a bulk action in the UI, the backend will now:
1.  **Create a Task Ledger entry** in Firestore for each business.
2.  **Enqueue a Cloud Task** into a managed queue.
3.  **Return "Accepted"** to the UI immediately.

---

## 2. Phase 1: Backend Infrastructure (✅ COMPLETED)

### A. The Task Ledger (`tasks` collection)
We now have a record of "Who is doing what."
*   **Implementation:** `packages/db/hephae_db/firestore/tasks.py`
*   **Fields:** `businessId`, `taskType`, `status`, `progress`, `error`.

### B. The Cloud Task Enqueuer
*   **Implementation:** `apps/api/backend/lib/tasks.py`
*   **Endpoint:** `POST /api/research/tasks/spawn`
*   **Benefit:** Provides automatic retries and rate-limiting.

---

## 3. Phase 2: Agentic Dispatcher (✅ COMPLETED)

We now use a **Dispatcher Agent** to pick up the task.
*   **Implementation:** `apps/api/backend/workflows/agents/discovery/dispatcher.py`
*   **Intelligence:** Decision-making logic to skip redundant steps.
*   **Grounding:** Integrated with the flywheel plan.

---

## 4. Phase 3: UI "Heartbeat" Updates (P1)

We will update **`BusinessBrowser.tsx`** to show the state of these background tasks.

1.  **Task Icons:** Instead of a generic "Analyzed" badge, we show:
    *   🕒 (Queued)
    *   ⚙️ (Agent Thinking...)
    *   ✅ (Done)
2.  **Live Updates:** The UI will poll the `tasks` collection (or use a Firestore listener) so you see the spinners turn into checkmarks in real-time across all 20 rows.

---

## 5. Summary Table: Why this is the "Agentic Way"

| Feature | Impact | Why it's "Agentic" |
| :--- | :--- | :--- |
| **Cloud Tasks** | Reliability | Prevents model rate-limits from killing the UI. |
| **Dispatcher** | Efficiency | LLM decides which agents *actually* need to run. |
| **Task Ledger** | Transparency | You can audit exactly why a specific agent failed. |
| **Example Store**| Consistency | Every UI-spawned task uses "Gold Standard" logic. |

---

## 🏗️ Next Step: The "Spawn" Endpoint
I will implement `POST /api/research/tasks/spawn` which will be the new target for your UI's `handleBulk` function.

**Would you like me to start by creating the `tasks.py` enqueuer and the Firestore schema for the Task Ledger?**
