"""Admin routers."""

from datetime import datetime
from typing import Any


def _serialize(obj: Any) -> Any:
    """Serialize a dict or Pydantic model to JSON-safe dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj
