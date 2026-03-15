# Hephae Forge: System Architecture

**Status**: Production Spec (v1.0)
**Last Updated**: 2026-03-14

---

## 1. System Vision: The "Modular Agent Factory"

Hephae Forge is an AI-agent orchestration engine designed to discover, qualify, and analyze independent local businesses. It transforms raw internet data into "Enterprise-Grade" intelligence reports (SEO, Social, Margins).

The architecture follows a strict **Domain-Driven Design (DDD)**:
- **`agents/`**: The Intelligence. Stateless AI agents (ADK) that perform specialized analysis.
- **`lib/`**: The Plumbing. Shared models, database logic, and external API integrations.
- **`apps/api/`**: The Controller. Orchestrates workflows and exposes the Unified API.
- **`skills/`**: The Knowledge. Industry-specific configurations (YAML) that parameterize the agents.

---

## 2. The 3-Tier Discovery Pipeline

To maximize cost-efficiency ($0.50/lead reduced to <$0.10/lead), the system uses a tiered "Sieve" architecture.

### Tier 1: Broad Scan (High Volume, Low Cost)
- **Goal**: Find 50-100 business names and addresses in a zipcode.
- **Sources**: OSM (OpenStreetMap), Google Search (broad snippets), Municipal Hubs.
- **Output**: "Light" business profiles (Name, Address, Category, Website URL).

### Tier 2: Qualification Sieve (The "Filter")
- **Goal**: Discard chains and low-value targets before spending AI compute.
- **Logic**: Lightweight HTTP probes check for `robots.txt`, CMS platforms (Shopify/Toast), and tracking pixels.
- **Tracks**:
    - **QUALIFIED**: Move to Tier 3 analysis.
    - **QUALIFIED_ACTION_REQUIRED**: High-reputation but no website. Pitch: "You need a website."
    - **PARKED**: Low maturity, save for future batch lookup.
    - **DISQUALIFIED**: National chains or closed businesses.

### Tier 3: Deep Discovery (High Value, Targetted)
- **Goal**: Multi-agent analysis only for high-value targets.
- **Agents**: SEO Auditor, Margin Surgeon, Social Media Auditor, Traffic Forecaster.
- **Pattern**: "State-First"—agents skip redundant crawling if Tier 2 already found the data.

---

## 3. Infrastructure & Scaling

- **Orchestration**: Built on **Google Agent Development Kit (ADK)** using Gemini models.
- **Task Management**: Uses **GCP Cloud Tasks** for "Fan-Out" processing.
    - `hephae-qualification-queue`: 5 dispatches/sec (lightweight HTTP).
    - `hephae-agent-queue`: 15s staggered delay (heavyweight AI analysis).
- **Persistence**: 
    - **Firestore**: Real-time business state and workflow progress.
    - **BigQuery**: Longitudinal data for market benchmarks and AI calibration.

---

## 4. The Compounding Loop

The system gets smarter with every run:
1. **Record**: Every business outcome (success/failure) is saved to the Knowledge Store.
2. **Calibrate**: A **Calibration Agent** periodically analyzes outcomes to update "Industry Benchmarks."
3. **Inform**: Future runs use these benchmarks to adjust qualification weights (e.g., if Instagram is the #1 predictor of success for Barbers, its weight is auto-increased).
