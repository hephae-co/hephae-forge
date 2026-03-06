"""Shared helpers for Google ADK Python SDK."""

from __future__ import annotations

from google.genai import types


def user_msg(text: str) -> types.Content:
    """Build a simple text Content for runner.run_async(new_message=...)."""
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def user_msg_with_image(text: str, image_b64: str, mime_type: str = "image/jpeg") -> types.Content:
    """Build a Content with text + inline image data.

    The Blob constructor accepts a base64 string directly and decodes it internally.
    """
    return types.Content(
        role="user",
        parts=[
            types.Part.from_text(text=text),
            types.Part(inline_data=types.Blob(data=image_b64, mime_type=mime_type)),
        ],
    )
