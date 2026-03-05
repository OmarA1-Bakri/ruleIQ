"""
Google Gemini AI Provider

Implements the AIProvider interface for Google's Gemini models.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from google.genai.types import HarmCategory, HarmBlockThreshold

from config.ai_config import get_ai_model
from services.ai.circuit_breaker import AICircuitBreaker
from services.ai.analytics_monitor import get_analytics_monitor, MetricType
from .base import (
    AIProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderQuotaError
)

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini AI provider implementation."""

    def __init__(
        self,
        circuit_breaker: Optional[AICircuitBreaker] = None,
        analytics_monitor: Optional[Any] = None,
        cached_content_manager: Optional[Any] = None
    ) -> None:
        """
        Initialize the Gemini provider.

        Args:
            circuit_breaker: Circuit breaker for resilience
            analytics_monitor: Analytics monitoring service
            cached_content_manager: Cached content management service
        """
        self.circuit_breaker = circuit_breaker or AICircuitBreaker()
        self.analytics_monitor = analytics_monitor
        self.cached_content_manager = cached_content_manager

        # Default safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        self.model = None

    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """
        Generate a response using Gemini.

        Args:
            prompt: The input prompt
            config: Provider configuration

        Returns:
            ProviderResponse with generated content

        Raises:
            ProviderUnavailableError: If Gemini is unavailable
            ProviderTimeoutError: If request times out
            ProviderQuotaError: If quota is exceeded
        """
        # Validate configuration
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        # Check circuit breaker
        model_name = config.model_name
        if not self.circuit_breaker.is_model_available(model_name):
            raise ProviderUnavailableError(f"Gemini model {model_name} is unavailable")

        # Initialize analytics monitor if needed
        if not self.analytics_monitor:
            self.analytics_monitor = await get_analytics_monitor()

        try:
            # Get or create model
            if not self.model or self.model.model_name != model_name:
                self.model = get_ai_model(model_name)

            # Attach cached content if provided
            if config.cached_content:
                self.model._cached_content = config.cached_content
                logger.debug("Attached cached content to Gemini model")

            # Build generation config
            generation_config = {
                'temperature': config.temperature,
                'top_p': 0.8,
                'top_k': 20
            }
            if config.max_tokens:
                generation_config['max_output_tokens'] = config.max_tokens

            # Override safety settings if provided
            safety_settings = config.safety_settings or self.safety_settings

            # Record start time
            start_time = datetime.now(timezone.utc)

            # Generate response with timeout
            try:
                # Run generation in thread pool to avoid blocking
                generation_task = asyncio.create_task(
                    asyncio.to_thread(
                        self.model.generate_content,
                        prompt,
                        safety_settings=safety_settings,
                        generation_config=generation_config
                    )
                )

                response = await asyncio.wait_for(
                    generation_task,
                    timeout=config.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Gemini generation timed out after {config.timeout}s")
                raise ProviderTimeoutError(
                    f"Gemini request timed out after {config.timeout}s"
                )

            # Record end time
            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds()

            # Extract response text
            response_text = self._extract_response_text(response)

            # Extract function calls if present
            function_calls = self._extract_function_calls(response)

            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            estimated_tokens = len(prompt) // 4 + len(response_text) // 4

            # Record analytics
            if self.analytics_monitor:
                await self.analytics_monitor.record_metric(
                    MetricType.RESPONSE_TIME,
                    'gemini_generation',
                    response_time,
                    metadata={
                        'model': model_name,
                        'tokens': estimated_tokens,
                        'has_cached_content': config.cached_content is not None
                    }
                )

            # Build provider response
            provider_response = ProviderResponse(
                text=response_text,
                model_used=model_name,
                tokens_used=estimated_tokens,
                finish_reason=self._get_finish_reason(response),
                function_calls=function_calls,
                metadata={
                    'response_time_ms': int(response_time * 1000),
                    'safety_ratings': self._extract_safety_ratings(response)
                },
                cached=config.cached_content is not None
            )

            logger.info(
                f"Gemini response generated in {response_time:.2f}s "
                f"({estimated_tokens} tokens)"
            )

            return provider_response

        except Exception as e:
            error_str = str(e).lower()

            # Handle quota errors
            if 'quota' in error_str or '429' in error_str or 'resource_exhausted' in error_str:
                logger.error(f"Gemini quota exceeded: {e}")
                raise ProviderQuotaError(f"Gemini quota exceeded: {e}")

            # Handle other errors
            logger.error(f"Gemini generation failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"Gemini generation failed: {e}")

    async def generate_stream(
        self,
        prompt: str,
        config: ProviderConfig
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response using Gemini.

        Args:
            prompt: The input prompt
            config: Provider configuration

        Yields:
            Text chunks as they arrive
        """
        if not self.validate_config(config):
            raise ValueError("Invalid provider configuration")

        model_name = config.model_name
        if not self.circuit_breaker.is_model_available(model_name):
            raise ProviderUnavailableError(f"Gemini model {model_name} is unavailable")

        try:
            if not self.model or self.model.model_name != model_name:
                self.model = get_ai_model(model_name)

            generation_config = {
                'temperature': config.temperature,
                'top_p': 0.8,
                'top_k': 20,
            }
            if config.max_tokens:
                generation_config['max_output_tokens'] = config.max_tokens

            safety_settings = config.safety_settings or self.safety_settings
            timeout_seconds = config.timeout or 30.0

            queue: asyncio.Queue[Any] = asyncio.Queue()
            sentinel = object()
            loop = asyncio.get_running_loop()

            def _producer() -> None:
                try:
                    response = self.model.generate_content(
                        prompt,
                        safety_settings=safety_settings,
                        generation_config=generation_config,
                        stream=True,
                    )
                    for chunk in response:
                        if hasattr(chunk, 'text') and chunk.text:
                            loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, exc)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, sentinel)

            producer_task = asyncio.create_task(asyncio.to_thread(_producer))

            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    producer_task.cancel()
                    try:
                        await asyncio.wait_for(producer_task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                    logger.error(
                        "Gemini streaming timed out after %ss (model=%s)",
                        timeout_seconds,
                        model_name,
                    )
                    raise ProviderUnavailableError(
                        f"Gemini streaming timed out after {timeout_seconds}s"
                    )

                if item is sentinel:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item

            await asyncio.wait_for(producer_task, timeout=timeout_seconds)

        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}", exc_info=True)
            raise ProviderUnavailableError(f"Gemini streaming failed: {e}")

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        # Check if circuit breaker allows Gemini models
        return self.circuit_breaker.is_model_available("gemini-1.5-flash")

    def get_model_name(self) -> str:
        """Get current model name."""
        if self.model:
            return getattr(self.model, 'model_name', 'unknown')
        return 'gemini-1.5-flash'

    def _extract_response_text(self, response) -> str:
        """Extract text from Gemini response."""
        try:
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts
                    return ''.join(part.text for part in parts if hasattr(part, 'text'))
            return ''
        except Exception as e:
            logger.error(f"Failed to extract response text: {e}")
            return ''

    def _extract_function_calls(self, response) -> list:
        """Extract function calls from Gemini response."""
        function_calls = []
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            fc = part.function_call
                            function_calls.append({
                                'name': fc.name,
                                'args': dict(fc.args) if hasattr(fc, 'args') else {}
                            })
        except Exception as e:
            logger.error(f"Failed to extract function calls: {e}")

        return function_calls

    def _get_finish_reason(self, response) -> str:
        """Get finish reason from Gemini response."""
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    return str(candidate.finish_reason)
        except Exception:
            pass
        return 'stop'

    def _extract_safety_ratings(self, response) -> dict:
        """Extract safety ratings from Gemini response."""
        ratings = {}
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'safety_ratings'):
                    for rating in candidate.safety_ratings:
                        ratings[str(rating.category)] = str(rating.probability)
        except Exception as e:
            logger.error(f"Failed to extract safety ratings: {e}")
        return ratings
