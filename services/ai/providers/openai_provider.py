"""
OpenAI Provider

Implements the AIProvider interface for OpenAI models.
"""

import asyncio
import json
import logging
import os
import threading
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from .base import (
    AIProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderQuotaError,
    queue_put_with_backpressure,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""

    # Default model if none specified
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, circuit_breaker: Optional[Any] = None) -> None:
        """Initialize OpenAI provider."""
        self.circuit_breaker = circuit_breaker
        self._client = None
        self._api_key = os.getenv("OPENAI_API_KEY")
        logger.info("OpenAIProvider initialized")

    def _get_client(self) -> Any:
        """Get or create the OpenAI client (lazy initialization)."""
        if self._client is None:
            try:
                import openai

                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError:
                raise ProviderUnavailableError(
                    "openai package not installed. Run: pip install openai"
                )
            except Exception as e:
                raise ProviderUnavailableError(f"Failed to initialize OpenAI client: {e}")
        return self._client

    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """Generate response using OpenAI."""
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        model_name = config.model_name or self.DEFAULT_MODEL
        start_time = datetime.now(timezone.utc)

        try:
            client = self._get_client()

            # Build messages
            messages: list[dict[str, str]] = []
            if config.system_instruction:
                messages.append({"role": "system", "content": config.system_instruction})
            messages.append({"role": "user", "content": prompt})

            # Build request kwargs
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": config.temperature,
            }

            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens

            if config.tools:
                kwargs["tools"] = config.tools

            # Run synchronous API call in thread pool with timeout
            try:
                generation_task = asyncio.create_task(
                    asyncio.to_thread(
                        client.chat.completions.create,
                        **kwargs,
                    )
                )
                response = await asyncio.wait_for(generation_task, timeout=config.timeout)
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI generation timed out after {config.timeout}s")
                raise ProviderTimeoutError(f"OpenAI request timed out after {config.timeout}s")

            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds()

            # Extract response text
            response_text = ""
            if response.choices:
                message = response.choices[0].message
                response_text = message.content or ""

            # Extract token usage
            tokens_used = 0
            if hasattr(response, "usage") and response.usage:
                tokens_used = response.usage.total_tokens

            # Extract finish reason
            finish_reason = "stop"
            if response.choices:
                finish_reason = response.choices[0].finish_reason or "stop"

            # Extract function/tool calls
            function_calls = []
            if response.choices and response.choices[0].message.tool_calls:
                for tc in response.choices[0].message.tool_calls:
                    parsed_args: Any = tc.function.arguments
                    if isinstance(tc.function.arguments, str):
                        try:
                            parsed_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError as exc:
                            logger.warning(
                                "Failed to parse tool arguments for %s: %s",
                                tc.function.name,
                                exc,
                            )
                            parsed_args = {
                                "raw": tc.function.arguments,
                                "parse_error": str(exc),
                            }
                    function_calls.append(
                        {
                            "name": tc.function.name,
                            "args": parsed_args,
                        }
                    )

            provider_response = ProviderResponse(
                text=response_text,
                model_used=model_name,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                function_calls=function_calls,
                metadata={
                    "response_time_ms": int(response_time * 1000),
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0)
                    if response.usage
                    else 0,
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0)
                    if response.usage
                    else 0,
                },
                cached=False,
            )

            logger.info(f"OpenAI response generated in {response_time:.2f}s ({tokens_used} tokens)")
            return provider_response

        except (ProviderTimeoutError, ProviderUnavailableError, ProviderQuotaError):
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "quota" in error_str:
                logger.error(f"OpenAI quota exceeded: {e}")
                raise ProviderQuotaError(f"OpenAI quota exceeded: {e}")

            logger.error(f"OpenAI generation failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"OpenAI generation failed: {e}")

    async def generate_stream(
        self,
        prompt: str,
        config: ProviderConfig,
    ) -> AsyncIterator[str]:
        """Generate streaming response using OpenAI."""
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        model_name = config.model_name or self.DEFAULT_MODEL

        try:
            client = self._get_client()

            messages: list[dict[str, str]] = []
            if config.system_instruction:
                messages.append({"role": "system", "content": config.system_instruction})
            messages.append({"role": "user", "content": prompt})

            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": config.temperature,
                "stream": True,
            }

            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens

            timeout_seconds = config.timeout or 30.0
            stream = client.chat.completions.create(**kwargs)
            iterator = iter(stream)

            def _next_content_chunk(chunk_iterator: Any) -> tuple[bool, Any]:
                try:
                    chunk = next(chunk_iterator)
                except StopIteration:
                    return False, None

                if chunk.choices and chunk.choices[0].delta.content:
                    return True, chunk.choices[0].delta.content
                return True, None

            while True:
                try:
                    has_chunk, content = await asyncio.wait_for(
                        asyncio.to_thread(_next_content_chunk, iterator),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "OpenAI streaming timed out after %ss (model=%s)",
                        timeout_seconds,
                        model_name,
                    )
                    raise ProviderTimeoutError(
                        f"OpenAI streaming timed out after {timeout_seconds}s"
                    )

                if not has_chunk:
                    break
                if content:
                    yield content

        except Exception as e:
            if isinstance(e, (ProviderTimeoutError, ProviderUnavailableError, ProviderQuotaError)):
                raise
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "quota" in error_str:
                logger.error(f"OpenAI quota exceeded during streaming: {e}")
                raise ProviderQuotaError(f"OpenAI quota exceeded during streaming: {e}")
            logger.error(f"OpenAI streaming failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"OpenAI streaming failed: {e}")

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return bool(self._api_key)

    def get_model_name(self) -> str:
        """Get current model name."""
        return self.DEFAULT_MODEL

    def estimate_cost(self, tokens: int) -> float:
        """Estimate cost for OpenAI responses (defaults from env fallback, last verified 2026-03-04)."""
        input_per_m = float(os.getenv("OPENAI_GPT4O_INPUT_PER_M", "2.5"))
        output_per_m = float(os.getenv("OPENAI_GPT4O_OUTPUT_PER_M", "10.0"))
        blended_rate = (input_per_m + output_per_m) / 2
        return tokens * blended_rate / 1_000_000
