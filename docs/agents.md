# Hephae Agents: Intelligence Registry

This document lists the autonomous agents operating within the Hephae Forge. All agents are built using the **Google Agent Development Kit (ADK)** and use Gemini models.

---

## 1. Discovery & Qualification Agents

| Agent | Module | Role |
| :--- | :--- | :--- |
| **ZipcodeScanner** | `discovery` | Finds local businesses using Google Search grounding. Excludes national chains. |
| **HVTClassifier** | `qualification` | **The Sieve.** Uses lite models to decide if a business is a High-Value Target (HVT) based on metadata. |
| **LocatorAgent** | `discovery` | Precise entity matching. Confirms if a business name/address found online matches our internal records. |
| **WebsiteFinder** | `discovery` | Specifically tasked with finding the official URL for a "Digitally Invisible" business. |

---

## 2. Analysis Agents (The "Surgeons")

| Agent | Module | Role |
| :--- | :--- | :--- |
| **SeoAuditor** | `seo_auditor` | Technical SEO audit (Lighthouse, SSL, metadata). Finds gaps in search visibility. |
| **MarginSurgeon** | `margin_analyzer` | Benchmarks menu prices against regional data and commodity inflation (BLS). |
| **SocialMediaAuditor** | `social` | Analyzes Instagram/Facebook presence, posting frequency, and engagement. |
| **ForecasterAgent** | `traffic_forecaster` | Predicts customer foot traffic based on local events, weather, and industry trends. |
| **CompetitiveAnalyzer** | `competitive_analysis` | Maps the local landscape to find "Opportunity Gaps" where competitors are weak. |

---

## 3. Workflow & Review Agents

| Agent | Module | Role |
| :--- | :--- | :--- |
| **InsightsAgent** | `insights` | Synthesizes all capability reports into a 1-page "Executive Summary" for the business owner. |
| **ReviewerAgent** | `reviewer` | The **Internal Judge.** Checks all generated reports for hallucinations, tone, and accuracy before approval. |
| **CommunicatorAgent** | `outreach` | Drafts personalized, value-first emails based on the insights discovered. |
| **CalibrationAgent** | `skills` | Periodic agent that updates global market benchmarks based on successful/failed runs. |

---

## 4. Operational Pattern: "State-First"

Agents are designed to be **stateless**. They receive the `session.state` which contains all previously discovered data.
- **Rule**: If `state.email` exists from the qualification phase, the **CommunicatorAgent** will NOT perform a search; it will use the existing data.
- **Benefit**: Drastic reduction in API costs and execution latency.
