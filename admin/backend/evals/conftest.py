"""Shared pytest configuration for ADK agent evaluations."""

import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `backend.*` imports resolve
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Set a dummy GEMINI_API_KEY if not already set — required by google-adk
# to initialise agents, but evals use the real key when running live.
os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GOOGLE_GENAI_API_KEY", ""))
