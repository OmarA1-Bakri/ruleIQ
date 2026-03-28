"""
Backpressure tests for AI provider streaming.

These tests prove that provider generators yield incrementally instead of
running ahead and buffering chunks before the consumer requests them.
"""

import asyncio
import sys
import threading
import types
from unittest.mock import Mock

import pytest

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

if "config.logging_config" not in sys.modules:
    logging_stub = types.ModuleType("config.logging_config")
    logging_stub.get_logger = lambda name: Mock()
    sys.modules["config.logging_config"] = logging_stub

if "google" not in sys.modules:
    google_stub = types.ModuleType("google")
    sys.modules["google"] = google_stub

if "google.genai" not in sys.modules:
    genai_stub = types.ModuleType("google.genai")
    genai_stub.Client = Mock()
    sys.modules["google.genai"] = genai_stub

if "google.genai.types" not in sys.modules:
    genai_types_stub = types.ModuleType("google.genai.types")

    class _HarmCategory:
        HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
        HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
        HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
        HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"

    class _HarmBlockThreshold:
        BLOCK_ONLY_HIGH = "BLOCK_ONLY_HIGH"
        BLOCK_MEDIUM_AND_ABOVE = "BLOCK_MEDIUM_AND_ABOVE"

    genai_types_stub.HarmCategory = _HarmCategory
    genai_types_stub.HarmBlockThreshold = _HarmBlockThreshold
    sys.modules["google.genai.types"] = genai_types_stub

from services.ai.providers.anthropic_provider import AnthropicProvider
from services.ai.providers.base import ProviderConfig, ProviderTimeoutError
from services.ai.providers.gemini_provider import GeminiProvider
from services.ai.providers.openai_provider import OpenAIProvider


class _OpenAIChunk:
    def __init__(self, content):
        self.choices = [Mock(delta=Mock(content=content))]


class _GeminiChunk:
    def __init__(self, text):
        self.text = text


class _AnthropicStream:
    def __init__(self, started_event, first_advanced_event, release_second_event):
        self._started_event = started_event
        self._first_advanced_event = first_advanced_event
        self._release_second_event = release_second_event
        self.text_stream = self._text_stream()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def _text_stream(self):
        self._started_event.set()
        yield "alpha"
        self._first_advanced_event.set()
        if not self._release_second_event.wait(timeout=1.0):
            raise AssertionError("Anthropic stream advanced before consumer released backpressure")
        yield "beta"


async def _assert_incremental_stream(stream_factory, first_item, second_item):
    first_advanced_event = threading.Event()
    started_event = threading.Event()
    release_second_event = threading.Event()
    provider = stream_factory(started_event, first_advanced_event, release_second_event)

    generator = provider.generate_stream(
        "prompt",
        ProviderConfig(model_name="test-model", timeout=1.0),
    )

    first_task = asyncio.create_task(generator.__anext__())
    await asyncio.wait_for(asyncio.to_thread(started_event.wait, 1.0), timeout=1.0)
    await asyncio.sleep(0.05)

    assert started_event.is_set()
    assert not first_advanced_event.is_set()

    assert await first_task == first_item

    release_second_event.set()
    assert await asyncio.wait_for(generator.__anext__(), timeout=1.0) == second_item

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(generator.__anext__(), timeout=1.0)

    await generator.aclose()


class TestOpenAIProviderStreaming:
    @pytest.mark.asyncio
    async def test_generate_stream_backpressures_chunks(self):
        provider = OpenAIProvider()

        def stream_factory(started_event, first_advanced_event, release_second_event):
            fake_client = Mock()

            def _stream():
                started_event.set()
                yield _OpenAIChunk("alpha")
                first_advanced_event.set()
                if not release_second_event.wait(timeout=1.0):
                    raise AssertionError(
                        "OpenAI stream advanced before consumer released backpressure"
                    )
                yield _OpenAIChunk("beta")
                yield _OpenAIChunk(None)

            fake_client.chat.completions.create = Mock(return_value=_stream())
            provider._get_client = Mock(return_value=fake_client)
            return provider

        await _assert_incremental_stream(stream_factory, "alpha", "beta")


class TestAnthropicProviderStreaming:
    @pytest.mark.asyncio
    async def test_generate_stream_backpressures_chunks(self):
        provider = AnthropicProvider()

        def stream_factory(started_event, first_advanced_event, release_second_event):
            fake_client = Mock()
            fake_client.messages.stream = Mock(
                return_value=_AnthropicStream(
                    started_event,
                    first_advanced_event,
                    release_second_event,
                )
            )
            provider._get_client = Mock(return_value=fake_client)
            return provider

        await _assert_incremental_stream(stream_factory, "alpha", "beta")


class TestGeminiProviderStreaming:
    @pytest.mark.asyncio
    async def test_generate_stream_backpressures_chunks(self):
        provider = GeminiProvider()
        provider.circuit_breaker = Mock(is_model_available=Mock(return_value=True))

        def stream_factory(started_event, first_advanced_event, release_second_event):
            fake_model = Mock()
            fake_model.model_name = "test-model"

            def _stream(prompt, safety_settings=None, generation_config=None, stream=False):
                assert stream is True
                started_event.set()
                yield _GeminiChunk("alpha")
                first_advanced_event.set()
                if not release_second_event.wait(timeout=1.0):
                    raise AssertionError(
                        "Gemini stream advanced before consumer released backpressure"
                    )
                yield _GeminiChunk("beta")

            fake_model.generate_content = Mock(side_effect=_stream)
            provider.model = fake_model
            return provider

        await _assert_incremental_stream(stream_factory, "alpha", "beta")

    @pytest.mark.asyncio
    async def test_generate_stream_raises_timeout_error(self):
        provider = GeminiProvider()
        provider.circuit_breaker = Mock(is_model_available=Mock(return_value=True))
        provider.model = Mock(model_name="test-model")

        def _blocked_stream(*args, **kwargs):
            gate = threading.Event()
            yield _GeminiChunk("alpha")
            gate.wait(timeout=2.0)

        provider.model.generate_content = Mock(side_effect=_blocked_stream)
        generator = provider.generate_stream(
            "prompt",
            ProviderConfig(model_name="test-model", timeout=0.05),
        )

        first_chunk = await asyncio.wait_for(generator.__anext__(), timeout=1.0)
        assert first_chunk == "alpha"

        with pytest.raises(ProviderTimeoutError):
            await asyncio.wait_for(generator.__anext__(), timeout=1.0)

        await generator.aclose()
