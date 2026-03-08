# Agentic Design Review: Hephae-Forge (Discovery Deep-Dive)

## 1. Executive Summary: Robustness & Determinism
The current Discovery pipeline is sophisticated but relies heavily on the `ContactAgent` (LLM) to perform reasoning that could be handled deterministically. To achieve "non-hallucination" levels of accuracy while balancing cost, we must move from **"LLM-as-Extractor"** to **"LLM-as-Researcher"**.

---

## 2. Priority 0: Discovery Robustness Updates

### P0.1: Deterministic "Contact-First" Pass
*   **Current Issue:** `ContactAgent` uses LLM tokens to scan `rawSiteData` for emails/phones. This is expensive and prone to skipping patterns.
*   **Action:** 
    1.  **Enhance Playwright Tool:** Update `crawl_web_page` in `shared_tools/playwright.py` to:
        *   Automatically detect and crawl `/contact` or `/about` pages if email/phone is missing from the homepage.
        *   Use a robust Python-based regex engine (e.g., `phonenumbers` and `email-validator`) on the raw HTML *before* the LLM sees it.
    2.  **Toolified Extraction:** Pass the deterministic results into the `session.state`. The `ContactAgent` then only runs if data is *missing*, acting as a researcher (using Google Search) rather than a parser.
*   **Benefit:** 100% deterministic for on-page data; 0% hallucination risk for found emails/phones.

### P0.2: Dedicated "Challenges & Pain Points" Agent
*   **Current Issue:** Challenges are buried in a general "AI Overview." There is no dedicated logic to find what's *wrong* with a business.
*   **Action:** Add a new sub-agent to the `DiscoveryFanOut`: **`ChallengesAgent`**.
    *   **Search Strategy:** 
        1.  `"{business_name} {city} reviews complaints"`
        2.  `"{business_name} {city} health inspection report"`
        3.  `"{business_name} {city} news lawsuit controversy"`
        4.  `"{business_name} {city} Better Business Bureau"`
    *   **Logic:** This agent specifically looks for negative sentiment, structural challenges (e.g., "parking is impossible," "slow service," "high turnover"), and regulatory issues.
*   **Benefit:** Provides the "deterministic" grit needed for business evaluation without relying on general LLM knowledge.

### P0.3: Entity Resolution Gate
*   **Current Issue:** Research starts immediately on any URL, even if it's the wrong business or an aggregator (Yelp/TripAdvisor).
*   **Action:** Implement a **Matcher Agent** that compares the input Name/Address with the crawled site's Title/Footer before triggering the Fan-Out.
*   **Benefit:** Prevents 100% of the cost/error associated with researching the "wrong" business.

---

## 3. Priority 1: Leveraging Existing Ecosystem (MCP & Skills)

### P1.1: Integrate Google Maps Reviews MCP
*   **Resource:** `google-maps-reviews-mcp` (GitHub)
*   **Use Case:** Use this specialized server to fetch and **summarize customer sentiment** deterministically. 
*   **Benefit:** Replaces the expensive "SocialProfiler" LLM scan with a targeted, grounded review summary.

### P1.2: Crawl4AI Agentic Patterns
*   **Resource:** `llm-web-scraper` / `local-leads-finder` (GitHub)
*   **Strategy:** Adopt the "Planner → Executor" pattern from these projects. The Planner identifies missing fields (e.g., "Email is missing"), and the Executor (Crawl4AI) is given a targeted instruction to "find the email on the /contact page."
*   **Benefit:** More efficient than a "blind" crawl of 10 pages.

---

## 4. Priority 2: Cost & Efficiency (The "Context Diet")

### P2.1: Multi-Turn Stage Gating
*   **Action:** Use ADK's `LoopAgent` to skip agents if data exists in `session.state`. 
    *   If `Phone` is found by Playwright (Stage 1) -> Skip `ContactAgent` (Stage 2).
*   **Benefit:** Saves ~20-40% in token costs per business.

---

## 5. Summary Implementation Roadmap

| Stage | Name | Mode | Responsibility | Key Tool/MCP |
| :--- | :--- | :--- | :--- | :--- |
| **0** | **Matcher Gate** | **Agentic** | Entity Resolution (Name/Address Match) | Brave Search MCP |
| **1** | **SiteCrawler** | **Deterministic** | Playwright + Regex for Contacts/Socials | `shared_tools/playwright.py` |
| **2** | **Fan-Out** | **Gated** | **ChallengesAgent**, News, Competitors | Google Maps Reviews MCP |
| **3** | **SocialProfiler** | **Agentic** | Targeted engagement metrics | Crawl4AI |
| **4** | **Reviewer** | **Critic** | Cross-reference Stage 1 vs Stage 2 | ADK SequentialAgent |
