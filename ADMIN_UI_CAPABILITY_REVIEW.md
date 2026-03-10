# Admin UI Capability Audit: Batch Scheduling & Progress

This review analyzes the current state of the Admin UI regarding your request for **Scheduling** and **Progress Monitoring** of batch jobs.

---

## 1. Current State: "Live Pipeline Monitoring"
Your Admin UI already has an excellent **`DiscoveryProgress.tsx`** component.
*   **What it does:** It provides a real-time, phase-by-step visualization of a **single zip code scan** (Planning → Scanning → Verifying → Scoring).
*   **The Logic:** It polls `/api/research/discovery-status?zipCode=...` and updates a progress bar with icon-based states.

---

## 2. The Gap: "Batch Job Management"
While you can monitor a *live* scan, the UI is currently missing the **Scheduling Dashboard** for the `discovery_jobs` collection we discussed.

### Missing Features in UI:
1.  **Job Creation Form:** A way to input multiple zip codes and business types into a `CreateJobRequest`.
2.  **Job History Table:** A list of past and pending jobs (from `GET /api/admin/discovery-jobs`).
3.  **Approval Interface:** A "Review Required" dashboard where you can see the **Supervisor Summary** and click "Approve" for outreach.

---

## 3. Implementation Plan: The "Batch Command Center"

I recommend creating a new tab in your Admin UI called **"Batch Sweeps"**.

### P0: Job Creation & Status Table
*   **Component:** `BatchJobDashboard.tsx`
*   **Functionality:**
    *   **Form:** Input list of Zips (e.g., `07042, 07110, 07003`) and Sector (e.g., `Bakery`).
    *   **Table:** Shows Job Name, Status (`pending`, `running`, `review_required`), and "Run Now" button.

### P1: The "Supervisor Summary" Modal
*   **Functionality:** When a job is in `review_required`, clicking it opens a modal showing the **`automatedBatchSummary`** (Track 1) and a list of the leads found.
*   **Button:** "Approve for Outreach" — This hits the backend to move the job to `outreach_pending`.

### P1: Schedule Integration
*   **Functionality:** Add a "Repeat" dropdown to the job form (None, Daily, Weekly).
*   **Backend Sync:** This will update the Cloud Scheduler config or a `nextRunAt` field in Firestore.

---

## 4. Summary: Can you do it today?
*   **Schedule from UI:** **No.** You currently have to use a tool like Postman or me (Gemini CLI) to hit the `POST /api/admin/discovery-jobs` endpoint.
*   **See Progress from UI:** **Partially.** You can see the progress of an *active* zip scan if you know the zip code, but you cannot see the progress of a "Cloud Run Job" that is processing 10 zip codes in a row.

**Would you like me to build the `BatchJobDashboard.tsx` component for you to enable scheduling and multi-zip monitoring?**
