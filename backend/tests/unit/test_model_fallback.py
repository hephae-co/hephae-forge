"""Tests for model fallback utility."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.lib.model_fallback import (
    _is_retriable,
    fallback_on_error,
    generate_with_fallback,
)


class TestIsRetriable:
    def test_429_api_error(self):
        exc = MagicMock()
        exc.__class__.__name__ = "APIError"
        exc.code = 429
        # Patch the isinstance check
        with patch("backend.lib.model_fallback.genai_errors") as mock_errors:
            mock_errors.APIError = type(exc)
            exc.__class__ = mock_errors.APIError
            assert _is_retriable(exc) is True

    def test_429_in_string(self):
        exc = Exception("429 Resource exhausted")
        assert _is_retriable(exc) is True

    def test_503_in_string(self):
        exc = Exception("503 Service Unavailable")
        assert _is_retriable(exc) is True

    def test_resource_exhausted(self):
        exc = Exception("Resource exhausted for model")
        assert _is_retriable(exc) is True

    def test_non_retriable(self):
        exc = Exception("Invalid argument: bad prompt")
        assert _is_retriable(exc) is False

    def test_400_not_retriable(self):
        exc = Exception("400 Bad Request")
        assert _is_retriable(exc) is False


class TestFallbackOnError:
    @pytest.mark.asyncio
    async def test_returns_none_for_non_retriable(self):
        error = Exception("Invalid argument")
        result = await fallback_on_error(MagicMock(), MagicMock(), error)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_model(self):
        error = Exception("429 Resource exhausted")
        request = MagicMock()
        request.model = "some-unknown-model"
        result = await fallback_on_error(MagicMock(), request, error)
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_fallback_on_429(self):
        from google.genai.types import Content, Part

        error = Exception("429 Resource exhausted")
        request = MagicMock()
        request.model = "gemini-3.1-flash-lite-preview"
        request.contents = [MagicMock()]
        request.config = MagicMock()

        mock_content = Content(role="model", parts=[Part(text="fallback response")])
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content = mock_content
        mock_response.candidates[0].grounding_metadata = None

        with patch("backend.lib.model_fallback.genai") as mock_genai:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.Client.return_value = mock_client

            result = await fallback_on_error(MagicMock(), request, error)
            assert result is not None
            mock_client.aio.models.generate_content.assert_called_once()
            call_kwargs = mock_client.aio.models.generate_content.call_args
            assert call_kwargs.kwargs["model"] == "gemini-2.5-flash-lite"


class TestGenerateWithFallback:
    @pytest.mark.asyncio
    async def test_returns_primary_on_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await generate_with_fallback(
            mock_client, model="gemini-3.1-flash-lite-preview", contents="test"
        )
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_falls_back_on_429(self):
        mock_client = MagicMock()
        mock_fallback_response = MagicMock()

        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 Resource exhausted")
            return mock_fallback_response

        mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)

        result = await generate_with_fallback(
            mock_client, model="gemini-3.1-flash-lite-preview", contents="test"
        )
        assert result == mock_fallback_response
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_non_retriable(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("400 Bad Request")
        )

        with pytest.raises(Exception, match="400 Bad Request"):
            await generate_with_fallback(
                mock_client, model="gemini-3.1-flash-lite-preview", contents="test"
            )
