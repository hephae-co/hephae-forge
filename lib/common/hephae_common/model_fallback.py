"""Model fallback for 429 / model-unavailable errors.

Two mechanisms:
  1. fallback_on_error — ADK on_model_error_callback for LlmAgent
  2. generate_with_fallback — wrapper for direct genai.Client calls
"""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from hephae_common.model_config import MODEL_FALLBACK_MAP
from hephae_common.gemini_client import get_genai_client

logger = logging.getLogger(__name__)

_RETRIABLE_CODES = {404, 429, 503, 529}


def _is_retriable(exc: Exception) -> bool:
    """Check if exception is a retriable API error (429, 503, 529)."""
    if isinstance(exc, genai_errors.APIError):
        return getattr(exc, "code", 0) in _RETRIABLE_CODES
    msg = str(exc)
    return "429" in msg or "Resource exhausted" in msg or "503" in msg


async def fallback_on_error(
    callback_context: Any,
    llm_request: LlmRequest,
    error: Exception,
) -> LlmResponse | None:
    """ADK on_model_error_callback — retry with fallback model on 429/503/529.

    Returns LlmResponse on success, None to let error propagate.
    """
    if not _is_retriable(error):
        return None

    primary_model = llm_request.model
    fallback_model = MODEL_FALLBACK_MAP.get(primary_model)

    if not fallback_model:
        logger.warning(f"[ModelFallback] No fallback for {primary_model}: {error}")
        return None

    logger.warning(f"[ModelFallback] {primary_model} → {fallback_model} on {error}")

    try:
        client = get_genai_client()

        # Strip response_mime_type when tools are present — Gemini rejects the combo
        config = llm_request.config
        has_tools = bool(getattr(llm_request, "tools", None))
        if has_tools and config:
            config_dict = config.model_dump() if hasattr(config, "model_dump") else (dict(config) if config else {})
            if config_dict.get("response_mime_type"):
                config_dict.pop("response_mime_type", None)
                config_dict.pop("response_schema", None)
                from google.genai.types import GenerateContentConfig
                config = GenerateContentConfig(**{k: v for k, v in config_dict.items() if v is not None})

        response = await client.aio.models.generate_content(
            model=fallback_model,
            contents=llm_request.contents,
            config=config,
        )

        content = response.candidates[0].content if response.candidates else None
        grounding = (
            getattr(response.candidates[0], "grounding_metadata", None)
            if response.candidates
            else None
        )

        logger.info(f"[ModelFallback] Fallback {fallback_model} succeeded.")
        return LlmResponse(content=content, grounding_metadata=grounding)
    except Exception as fallback_err:
        logger.error(f"[ModelFallback] Fallback {fallback_model} also failed: {fallback_err}")
        return None


async def generate_with_fallback(
    client: genai.Client,
    model: str,
    contents: Any,
    config: Any = None,
    **kwargs,
) -> Any:
    """Wrapper for direct genai calls — auto-fallback on 429/unavailable."""
    try:
        return await client.aio.models.generate_content(
            model=model, contents=contents, config=config, **kwargs,
        )
    except (genai_errors.APIError, Exception) as e:
        if not _is_retriable(e):
            raise
        fallback = MODEL_FALLBACK_MAP.get(model)
        if not fallback:
            raise
        logger.warning(f"[ModelFallback] {model} → {fallback} on {e}")
        return await client.aio.models.generate_content(
            model=fallback, contents=contents, config=config, **kwargs,
        )
