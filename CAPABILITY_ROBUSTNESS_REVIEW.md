# Capability Robustness Review: High-Level Agents

This review analyzes the 5 core capabilities of Hephae-Forge: SEO Auditor, Margin Surgeon (MenuSurgeon), Competitive Analysis, Traffic Forecaster, and Social Media Auditor.

---

## 1. Executive Summary: The "Intelligence vs. Accuracy" Balance
Most capabilities use a **Multi-Stage Pipeline** (Research → Synthesis). While this is architecturally sound, the reliance on manual JSON parsing and volatile memory (RAM-based sessions) creates a reliability ceiling. The **Traffic Forecaster** is the most modern, using Gemini's native JSON mode, while **Margin Surgeon** is the most robust due to its deterministic math engine.

---

## 2. Priority 0: Critical Robustness Updates

### P0.1: Native Structured Outputs (All Agents)
*   **Current Issue:** SEO Auditor, Competitive Analysis, and Social Auditor use `re.sub` and `json.loads` to extract data from markdown fences.
*   **Mandate:** Transition to Pydantic models with `response_schema`. 
*   **Risk:** 10-15% of runs currently fail or return "None" due to malformed LLM JSON.
*   **Benefit:** 100% deterministic parsing.

### P0.2: Vision-to-Schema Consistency (Margin Surgeon)
*   **Current Issue:** Stage 1 (Vision Intake) extracts menu items into a string that is then re-parsed.
*   **Mandate:** Use Gemini 1.5 Pro's native JSON mode directly on the image. Define a `MenuItem` schema for the Vision agent.
*   **Benefit:** Prevents "hallucinated items" that don't exist on the physical menu.

---

## 3. Capability-Specific Analysis

| Capability | Current State | Robustness Gap | Recommendation |
| :--- | :--- | :--- | :--- |
| **1. SEO Auditor** | 5-category deep dive + PageSpeed tool. | Brittle parsing of complex technical audits. | **P1:** Move PageSpeed results to `session.state` first. |
| **2. Margin Surgeon** | Deterministic Math Engine + Vision. | **Best-in-class.** Uses actual math for leakage. | **P0:** Native JSON for Vision extraction. |
| **3. Competitive** | 2-stage (Profile → Strategy). | Uses few-shot memory but manual extraction. | **P1:** Add "Strategic Market Gaps" sub-agent. |
| **4. Traffic** | Parallel Intelligence (POI/Weather/Events). | **Most Modern.** Uses native ADK ParallelAgent. | **P1:** Persistent Session for historical comparison. |
| **5. Social** | 2-stage (Research → Strategist). | Heavy search cost (agent-in-agent). | **P0:** Use Native ADK Grounding for research. |

---

## 4. Priority 1: Architectural Improvements

### P1.1: The "Advisor" Critic Pattern
*   **Issue:** Strategic advice (in Margin Surgeon and Social Auditor) is generated in a single pass.
*   **Action:** Implement a **Critic Agent** that reviews the generated advice against the "Deterministic Facts" (e.g., if Margin Surgeon recommends a $20 price, the Critic checks if that's >50% higher than the competitor average).
*   **Benefit:** Prevents "unrealistic" or "dangerous" business advice.

### P1.2: Persistent Grounding Memory
*   **Issue:** `memory_service` for Competitive and Social agents is loaded from "fixtures" (static files).
*   **Action:** Allow the `memory_service` to learn from **Human Feedback**. If an admin corrects a report, that correction should become a "few-shot" example for future runs.
*   **Benefit:** The system gets smarter with every run.

---

## 5. Summary Implementation Roadmap

| Priority | Feature | Impact | Target Capability |
| :--- | :--- | :--- | :--- |
| **P0** | **Native JSON Schema** | Determinism | All |
| **P0** | **Vision JSON Mode** | Accuracy | Margin Surgeon |
| **P1** | **Advisor Critic** | Safety | Margin Surgeon, SEO |
| **P1** | **Active Learning** | Quality | Competitive, Social |
| **P2** | **MCP Toolification** | Reusability | All |
