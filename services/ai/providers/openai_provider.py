"""
OpenAI Provider

Implements the AIProvider interface for OpenAI models.
"""

import logging
from typing import Any, AsyncIterator, Optional

from .base import (
    AIProvider,
    ProviderConfig,
    ProviderResponse
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI provider implementation."""

    def __init__(self, circuit_breaker: Optional[Any] = None) -> None:
        """Initialize OpenAI provider."""
        self.circuit_breaker = circuit_breaker
        logger.info("OpenAIProvider initialized (placeholder)")

    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """Generate response using OpenAI."""
        raise NotImplementedError("OpenAI provider not yet implemented")

    async def generate_stream(
        self,
        prompt: str,
        config: ProviderConfig
    ) -> AsyncIterator[str]:
        """Generate streaming response using OpenAI."""
        raise NotImplementedError("OpenAI streaming not yet implemented")

    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return False

    def get_model_name(self) -> str:
        """Get current model name."""
        return 'gpt-4'
