# Review: Discovery Coverage & Storage Logic

This review addresses the logic for maximizing business discovery coverage in a zip code and how multiple agent runs are persisted for historical analysis.

---

## 1. Discovery Coverage (The "Missing 180" Problem)

### Current State: Limited Snapshot
The `ZipcodeScannerAgent` is currently instructed to find **15-20 businesses** per run. It uses a single broad search query.
*   **Problem:** If a zip code has 200 businesses, a single run will only ever capture the "Top 10%" most SEO-optimized ones. Subsequent runs with the same prompt will likely return the same results (LLM bias toward popular hits).

### Recommendation: Incremental Category-Based Scanning
To find all 200 businesses, we must transition from "Broad Search" to **"Targeted Category Iteration."**

1.  **The "Category List" Tool:** Define a deterministic list of 20+ business categories (Bakery, Auto Repair, Dentist, HVAC, Cafe, etc.).
2.  **The Multi-Run Orchestrator:** Implement a loop that runs the `ZipcodeScannerAgent` once **per category**.
    *   *Run 1:* "Find all Bakeries in 07042"
    *   *Run 2:* "Find all Auto Repair shops in 07042"
3.  **Deduplication:** The `scan_zipcode` function already handles name-based deduplication using `_normalize_name`, so running multiple targeted scans will safely aggregate into a complete list.

### P0 Action: Update `scan_zipcode` to accept a `category` parameter.
Instead of a generic scan, the system should allow a **Batch Job** that iterates through a category registry to ensure 95%+ coverage of the zip code.

---

## 2. Storage & Historical Analysis (BigQuery)

### Current State: Hybrid Persistence
Your system already has a robust hybrid storage model in `agent_results.py`:
1.  **Firestore (`latestOutputs`):** Stores the "Single Source of Truth" for the UI. It is an **Upsert**—only the most recent run per agent is kept here.
2.  **BigQuery (`hephae.analyses`):** Stores an **Append-Only History**. Every single time an agent runs, a new row is added with a unique `analysis_id`.

### Recommendation: Enhancing the BQ Data Moat
*   **Version Tracking:** The `agent_version` is already tracked. This is critical for comparing how "Smart" the newer models are vs. older ones.
*   **Cross-Run Comparison:** Because BQ is append-only, you can write SQL queries to track a business's health over time (e.g., *"Is their SEO score improving month-over-month?"*).

---

## 3. P0/P1 Implementation Roadmap

| Priority | Feature | Impact | Implementation |
| :--- | :--- | :--- | :--- |
| **P0** | **Category Batching** | Coverage | Update `scan_zipcode` to loop through categories. |
| **P0** | **Incremental Persistence** | Reliability | Ensure each category-run saves to Firestore immediately. |
| **P1** | **Scan Heartbeat** | Freshness | Schedule a "Re-Scan" every 90 days to find new businesses. |
| **P1** | **BQ Analysis Views** | Insight | Create BQ views for "Business Score Trends" across multiple runs. |

---

## 4. Conclusion: Moving to "Total Discovery"
By shifting to a **Category-Based Batch Scan**, you move from a "Sampling Tool" to a "Comprehensive Database." Your storage logic is already well-designed for this, as BigQuery will naturally capture the growth of your data over time without losing historical context.

**Would you like me to update the `ZipcodeScannerAgent` and its runner to support this category-based batching logic?**
