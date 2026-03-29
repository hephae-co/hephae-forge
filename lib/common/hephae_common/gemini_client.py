"""Thread-safe singleton genai.Client.

Avoids creating multiple client instances across modules.
"""

from __future__ import annotations

import os
import threading

from google import genai

_lock = threading.Lock()
_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    """Return a shared genai.Client initialized for Vertex AI / GCP Auth.

    This uses Google Cloud project-based authorization (ADC), which is required
    for Gemini Pro/Enterprise plans on Vertex AI.
    """
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")

        if project_id:
            # Authorized via Vertex AI (GCP) — recommended for Pro/Enterprise plans
            _client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location
            )
        else:
            # Fallback: Let the SDK attempt to find credentials automatically (ADC)
            # or check if GEMINI_API_KEY exists as a last resort.
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                _client = genai.Client(api_key=api_key)
            else:
                # This will use Application Default Credentials (ADC)
                _client = genai.Client()

        return _client
