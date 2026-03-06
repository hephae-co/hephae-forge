# Hephae Admin Python Backend

This is the refactored backend for the Hephae Admin dashboard, built using **Python**, **FastAPI**, and the **Google Agent Development Kit (ADK)**.

## Prerequisites

- Python 3.10+
- Google Cloud SDK installed and authenticated
- Environment variables configured (see `.env.example`)

## Setup

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the backend:**
    ```bash
    uvicorn main:app --reload --port 8000
    ```

## API Endpoints

- `GET /api/cron/run-analysis?zip=10001`: Triggers the automated discovery -> deep dive -> outreach cycle.
- `POST /api/run-tests`: Executes the quality assurance test suite against MarginSurgeon.
- `GET /api/run-tests`: Fetches historical test run summaries.

## Agent Orchestration

The backend uses several specialized agents:
- **ZipcodeScanner:** Discovers new businesses in a target area.
- **Analyst:** Orchestrates deep dives into SEO, Foot Traffic, and Competitive data.
- **Evaluators:** (SEO, Traffic, Competitive) Perform QA on agent outputs to detect hallucinations.
- **Communicator:** Formats and sends outreach messages.

## Data Integration

- **Firestore:** Stores business profiles and latest agent outputs.
- **BigQuery:** Logs every analysis run for historical reporting and metrics.
- **Resend:** (Optional) Sends outreach emails to discovered businesses.
