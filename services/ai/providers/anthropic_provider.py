"""
Anthropic Provider

Implements the AIProvider interface for Anthropic Claude models.
"""

import logging
from typing import Any, AsyncIterator, Optional

from .base import (
    AIProvider,
    ProviderConfig,
    ProviderResponse
)

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider implementation."""

    def __init__(self, circuit_breaker: Optional[Any] = None) -> None:
        """Initialize Anthropic provider."""
        self.circuit_breaker = circuit_breaker
        logger.info("AnthropicProvider initialized (placeholder)")

    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """Generate response using Anthropic Claude."""
        raise NotImplementedError("Anthropic provider not yet implemented")

    async def generate_stream(
        self,
        prompt: str,
        config: ProviderConfig
    ) -> AsyncIterator[str]:
        """Generate streaming response using Anthropic."""
        raise NotImplementedError("Anthropic streaming not yet implemented")

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return False

    def get_model_name(self) -> str:
        """Get current model name."""
        return 'claude-3-opus'
