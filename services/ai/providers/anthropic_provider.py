"""
Anthropic Provider

Implements the AIProvider interface for Anthropic Claude models.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from .base import (
    AIProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderQuotaError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider implementation."""

    # Default model if none specified
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, circuit_breaker: Optional[Any] = None) -> None:
        """Initialize Anthropic provider."""
        self.circuit_breaker = circuit_breaker
        self._client = None
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        logger.info("AnthropicProvider initialized")

    def _get_client(self) -> Any:
        """Get or create the Anthropic client (lazy initialization)."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise ProviderUnavailableError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
            except Exception as e:
                raise ProviderUnavailableError(f"Failed to initialize Anthropic client: {e}")
        return self._client

    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """Generate response using Anthropic Claude."""
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        model_name = config.model_name or self.DEFAULT_MODEL
        start_time = datetime.now(timezone.utc)

        try:
            client = self._get_client()

            # Build request kwargs
            kwargs: dict[str, Any] = {
                "model": model_name,
                "max_tokens": config.max_tokens or 4096,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if config.system_instruction:
                kwargs["system"] = config.system_instruction

            # Run synchronous API call in thread pool with timeout
            try:
                generation_task = asyncio.create_task(
                    asyncio.to_thread(
                        client.messages.create,
                        **kwargs,
                    )
                )
                response = await asyncio.wait_for(
                    generation_task, timeout=config.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Anthropic generation timed out after {config.timeout}s")
                raise ProviderTimeoutError(
                    f"Anthropic request timed out after {config.timeout}s"
                )

            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds()

            # Extract response text
            response_text = ""
            if hasattr(response, "content") and response.content:
                text_blocks = [
                    block.text for block in response.content
                    if hasattr(block, "text")
                ]
                response_text = "".join(text_blocks)

            # Extract token usage
            tokens_used = 0
            if hasattr(response, "usage"):
                tokens_used = (
                    getattr(response.usage, "input_tokens", 0)
                    + getattr(response.usage, "output_tokens", 0)
                )

            # Extract finish reason
            finish_reason = getattr(response, "stop_reason", "stop") or "stop"

            provider_response = ProviderResponse(
                text=response_text,
                model_used=model_name,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                function_calls=[],
                metadata={
                    "response_time_ms": int(response_time * 1000),
                    "input_tokens": getattr(response.usage, "input_tokens", 0)
                    if hasattr(response, "usage") else 0,
                    "output_tokens": getattr(response.usage, "output_tokens", 0)
                    if hasattr(response, "usage") else 0,
                },
                cached=False,
            )

            logger.info(
                f"Anthropic response generated in {response_time:.2f}s "
                f"({tokens_used} tokens)"
            )
            return provider_response

        except (ProviderTimeoutError, ProviderUnavailableError, ProviderQuotaError):
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                logger.error(f"Anthropic quota exceeded: {e}")
                raise ProviderQuotaError(f"Anthropic quota exceeded: {e}")

            logger.error(f"Anthropic generation failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"Anthropic generation failed: {e}")

    async def generate_stream(
        self,
        prompt: str,
        config: ProviderConfig,
    ) -> AsyncIterator[str]:
        """Generate streaming response using Anthropic."""
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        model_name = config.model_name or self.DEFAULT_MODEL

        try:
            client = self._get_client()

            kwargs: dict[str, Any] = {
                "model": model_name,
                "max_tokens": config.max_tokens or 4096,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            if config.system_instruction:
                kwargs["system"] = config.system_instruction

            # Use Anthropic streaming API in a thread
            def _stream():
                with client.messages.stream(**kwargs) as stream:
                    for text in stream.text_stream:
                        yield text

            # Collect chunks from sync generator in thread pool
            chunks = await asyncio.to_thread(lambda: list(_stream()))
            for chunk in chunks:
                yield chunk

        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"Anthropic streaming failed: {e}")

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return bool(self._api_key)

    def get_model_name(self) -> str:
        """Get current model name."""
        return self.DEFAULT_MODEL

    def estimate_cost(self, tokens: int) -> float:
        """Estimate cost for Claude Sonnet (input + output average)."""
        # Claude Sonnet 4: $3/M input, $15/M output — use blended rate
        return tokens * 9.0 / 1_000_000
