# Review: Scheduled Actions & Autonomous Evolution

This review analyzes the existing `cron.py` and `discovery_jobs.py` logic and provides a roadmap for transitioning to a proactive, **OpenClaw-inspired** agentic scheduling model.

---

## 1. Current State: "Reactive Scheduling"
The current logic is "Push-based":
*   **Cron:** A fixed timer hits `/api/cron/run-analysis`. It is blind to the actual state of the businesses.
*   **Jobs:** A manual "Job" system triggers a Cloud Run batch. It requires human initiation.

---

## 2. OpenClaw Pattern: The "Autonomous Heartbeat"
In OpenClaw and advanced ADK patterns, scheduling isn't just a timer—it's an **Agentic Loop**.

### Recommendation: The "Business Heartbeat" Agent
Instead of a generic cron job, implement a specialized **Heartbeat Agent**.
*   **The Logic:** This agent "wakes up" every hour, scans your BigQuery/Firestore history, and **self-identifies** which businesses need action.
*   **Criteria for Action:**
    1.  *"This business hasn't been crawled in 30 days."* (Staleness signal)
    2.  *"A new news article was just found for Essex County."* (External trigger)
    3.  *"This business had a 'Failed' outreach 3 days ago; let's try a different channel."* (Self-healing signal)

---

## 3. Improving the "Discovery Job" System

### P0: From "Manual Job" to "Intelligent Queue"
The `DiscoveryJobs` should move toward a **Priority Queue** model.
*   **Action:** Add a `priority` field (1-10) to the `DiscoveryTargetInput`.
*   **Benefit:** High-value zip codes or urgent client requests get processed first by the Heartbeat Agent.

### P1: "Event-Driven" Triggers (Serverless Sidecars)
Currently, jobs are standalone. They should be linked to your **Area Research**.
*   **Action:** When an `AreaResearchOrchestrator` finishes, it should automatically emit a `ResearchCompletedEvent` that the scheduler picks up to start individual business discovery.

---

## 4. Technical Resilience: "Self-Healing Retries"
A common OpenClaw pattern is the **"Backoff-and-Reflect"** loop.
*   **Action:** If a scheduled outreach fails (as seen in your `cron.py` loop), don't just log it. 
*   **Agentic Fix:** The Scheduler triggers a "Diagnostic Agent" to check if the business website is down or if the email was invalid, and updates the `discoveryStatus` to "Invalid_Contact."

---

## 5. Summary Implementation Roadmap

| Feature | Current Approach | OpenClaw / Agentic Target | Priority |
| :--- | :--- | :--- | :--- |
| **Trigger** | Fixed Cron Timer | **Heartbeat Agent** (Data-driven) | **P1** |
| **Initiation** | Manual Admin Post | **Autonomous Workflow Spawning** | **P1** |
| **Error Handling**| Try/Except + Log | **Self-Healing Retries** | **P2** |
| **Logic** | Hardcoded loop | **Priority-based Queue** | **P0** |

### Immediate Step (P0):
Update the `discovery_jobs` schema to include `last_run_at` and `retry_count`. This allows the current system to at least handle failures gracefully before moving to a full Heartbeat Agent.

**Would you like me to draft the "Heartbeat Agent" logic that can replace the simple cron loop?**
