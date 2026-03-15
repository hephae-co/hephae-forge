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
    """Return a shared genai.Client, creating it once on first call."""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is not None:
            return _client
        api_key = os.environ.get("GEMINI_API_KEY", "")
        _client = genai.Client(api_key=api_key)
        return _client
