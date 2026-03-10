# Review & Recommendations: Background Research Agents

This review covers the **Zip Code**, **Area**, and **Sector** research agents that form the foundation of the Hephae-Forge intelligence layer.

---

## 1. Technical Analysis: ADK & Design Patterns

### Current State: Manual State-Machine Orchestration
The `AreaResearchOrchestrator` and `SectorResearchOrchestrator` are currently implemented as large, manual Python classes using `asyncio.gather`. 
*   **Problem:** This is "fragile" orchestration. If one task fails, the whole class must handle the exception manually. It doesn't leverage ADK's native "Chain" or "Parallel" primitives.

### Recommendation: The "Hierarchical Research Hub"
Transition the research logic from manual Python to **ADK Agentic Orchestration**.
*   **The Structure:**
    1.  **`ResearchOrchestrator` (SequentialAgent):** Manages the high-level phases (Resolve → Gather → Synthesize).
    2.  **`IntelligenceGatherer` (ParallelAgent):** Runs the 6+ data sources (BLS, FDA, News, Trends) in parallel.
*   **Benefit:** Native ADK error handling, better logging via the `Runner`, and the ability to easily "swap" or "add" a new data source agent without rewriting the orchestrator's core loop.

---

## 2. Prompt & Capability Improvements

### Current Issue: "Blind" Google Search
Most research agents (e.g., `ZipCodeResearchAgent`) rely on broad Google Search instructions. This leads to generic demographics that may be out of date.

### Recommendation: Tool-Specific "Specialist" Agents
Break the monolithic `ZipCodeResearchAgent` into **Specialist Sub-Agents** with dedicated tools:

#### A. The "Local Governance" Agent (New)
*   **Task:** Search for local city council minutes, zoning changes, or licensing requirements.
*   **Search Query:** `"{city} {state} recent zoning changes bakery"` or `"{city} business license requirements"`
*   **Value:** Tells the business if a new regulation is coming that might impact them.

#### B. The "Commercial Real Estate" Agent (New)
*   **Task:** Use a specialized tool or targeted search to find commercial vacancy rates or "Available Spaces" near the target area.
*   **Value:** Directly helps the business understand if the neighborhood is "Growing" or "Declining" based on storefront occupancy.

#### C. The "Mobility & Foot Traffic" Agent (New)
*   **Task:** Integrate with a mobility data provider or use targeted search for "Walk Score" and "Transit accessibility."
*   **Value:** Adds a deterministic score to the "Market Opportunity" section of the report.

---

## 3. Advanced ADK Patterns for Research

### P1: Research "Context Caching"
*   **Issue:** The `EnhancedAreaSummaryAgent` processes 8+ data sources, often exceeding 50,000 tokens.
*   **Action:** Use ADK's `ContextCacheConfig`. Cache the "Industry Analysis" and "BLS Data" (which are static for all zips in a county). 
*   **Benefit:** Saves ~40% in token costs when running research across multiple zip codes in the same sector.

### P1: Human-Annotated "Ground Truth"
*   **Action:** Implement a **Grounding Memory Service** for the `AreaSummaryAgent`. 
*   **Concept:** When an expert analyst manually corrects an area summary, that "Perfect Summary" is saved to a vector store. The agent then uses this as a **Few-Shot Example** for the next area research.
*   **Benefit:** The "Tone" and "Precision" of the research improve over time without prompt engineering.

---

## 4. Summary Table of New Research Agents

| Agent Name | Category | Primary Tool | Context Added |
| :--- | :--- | :--- | :--- |
| **GovernanceAgent** | **P1** | Google Search (Site-limited) | Zoning, local permits, regulations. |
| **VacancyAgent** | **P1** | Zillow/LoopNet Search | Commercial occupancy, rent trends. |
| **MobilityAgent** | **P2** | WalkScore / Transit API | Foot traffic potential, accessibility. |
| **DemographicExpert** | **P0** | Census/ACS MCP Server | 100% deterministic census data. |

---

## 5. Conclusion
By moving from "Manual Python" to "ADK Orchestration" and introducing **Specialist Agents** for niche data (Real Estate, Governance), the background research will move from "Interesting Statistics" to "Essential Business Intelligence."
