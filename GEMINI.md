# Hephae Forge: Development & Architectural Mandates

This document serves as the foundational guide for all AI-assisted development within the `hephae-forge` monorepo. It takes precedence over general defaults.

## Project Vision: "The Unified API"
The project is transitioning to a centralized architecture where a single FastAPI service (`apps/api`) serves both the Web (`apps/web`) and Admin (`apps/admin`) frontends.

### Core Tech Stack
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, `google-adk` (Agent Development Kit).
- **Frontend:** TypeScript, Next.js (App Router), Tailwind CSS.
- **Database:** Google Cloud Firestore (via `lib/db`).
- **AI Orchestration:** Gemini Pro/Flash (via `agents/`).

---

## 1. Repository Structure & Ownership

| Path | Purpose | Mandate |
| :--- | :--- | :--- |
| `apps/api/` | **Unified Backend** | All new API endpoints and business logic MUST go here. |
| `apps/web/` | Web Frontend | Next.js only. |
| `apps/admin/` | Admin Dashboard | Next.js frontend for internal workflows. |
| `lib/db/` | Data Access Layer | Centralized Firestore/BigQuery logic. |
| `lib/common/` | Shared Logic | Source of truth for Pydantic models (`hephae_common.models`). |
| `agents/` | AI Agents | Individual agent logic (SEO, Margin, etc.) using ADK. |
| `infra/contracts/` | Specifications | Markdown schemas that MUST be reflected in Pydantic models. |
| `tests/evals/` | Agent Evals | Specialized test suite for LLM agent performance. |

---

## 2. Coding Standards & Principles

### Data Integrity (Firestore)
- **Model First:** Never write to Firestore using raw dicts if a Pydantic model exists.
- **Pathing:** Use dotted paths for nested updates to prevent overwriting entire documents.
- **Schema Alignment:** Before changing `hephae_common.models`, verify the change against `infra/contracts/firestore-schema.md`.

### AI & LLM Orchestration
- **ADK Usage:** All "capabilities" must be implemented as `google-adk` agents or runners in `agents/`.
- **Model Configuration:** Use `AgentModels` from `hephae_common.model_config` for model selection (Enhanced vs. Lite).
- **Structured Output:** Prefer `response_mime_type: "application/json"` or ADK's structured output over manual regex/JSON extraction where feasible.

### Build Systems
- **Standard:** Use `hatch` as the primary Python build system.
- **Inconsistency Alert:** If you encounter `setuptools` (setup.py) or `egg-info` in app directories, treat them as technical debt to be unified into `hatch` configurations.

---

## 3. Critical Workflows

### Adding a New Capability
1. Define the schema in `infra/contracts/`.
2. Create Pydantic models in `hephae_common.models`.
3. Implement the agent in `agents/hephae_agents/<name>/`.
4. Create an evaluation in `tests/evals/<name>/` using `*.test.json` files.
5. Register a router in `apps/api/hephae_api/routers/`.

### Running Tests
- **All Tests:** `pytest` from the root.
- **Agent Evals:** `pytest tests/evals/test_agent_evals.py -v`.
- **Workflow Tests:** `pytest tests/workflows/`.

---

## 4. Known Gaps & Targeted Improvements
*Priority areas for future tasks:*
1. **Validation Enforcement:** Refactor `hephae_db.firestore.businesses.save_business` to enforce Pydantic validation.
2. **Model Consolidation:** Migrate remaining models from `apps/api/hephae_api/types.py` to `hephae_common.models`.
3. **Infrastructure Unification:** Centralize `infra/` configurations to prevent drift between Web and Admin deployments.

---

## 5. Security & Safety
- **Secrets:** Never commit `.env` or `.env.local`. Use `load_dotenv()` only for local development.
- **GCP:** All cloud operations must target the `hephae-co-dev` project unless otherwise specified.
