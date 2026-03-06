"""
Base AI Provider Classes

Defines the abstract base class and data structures for AI providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class ProviderConfig:
    """Configuration for an AI provider request."""

    model_name: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    system_instruction: Optional[str] = None
    tools: Optional[List[Dict]] = None
    cached_content: Optional[Any] = None
    safety_settings: Optional[Dict] = None
    timeout: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


@dataclass
class ProviderResponse:
    """Standardized response from an AI provider."""

    text: str
    model_used: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    function_calls: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return asdict(self)


class ProviderUnavailableError(Exception):
    """Raised when a provider is unavailable."""

    pass


class ProviderTimeoutError(Exception):
    """Raised when a provider request times out."""

    pass


class ProviderQuotaError(Exception):
    """Raised when a provider quota is exceeded."""

    pass


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate(self, prompt: str, config: ProviderConfig) -> ProviderResponse:
        """
        Generate a response from the AI model.

        Args:
            prompt: The input prompt
            config: Provider configuration

        Returns:
            ProviderResponse with the generated content

        Raises:
            ProviderUnavailableError: If provider is unavailable
            ProviderTimeoutError: If request times out
            ProviderQuotaError: If quota is exceeded
        """
        pass

    @abstractmethod
    async def generate_stream(self, prompt: str, config: ProviderConfig) -> AsyncIterator[str]:
        """
        Generate a streaming response from the AI model.

        Args:
            prompt: The input prompt
            config: Provider configuration

        Yields:
            Text chunks as they arrive

        Raises:
            ProviderUnavailableError: If provider is unavailable
            ProviderTimeoutError: If request times out
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is currently available.

        Returns:
            True if provider is available, False otherwise
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the current model name.

        Returns:
            Model name string
        """
        pass

    def validate_config(self, config: ProviderConfig) -> bool:
        """
        Validate provider configuration.

        Args:
            config: Provider configuration to validate

        Returns:
            True if valid, False otherwise
        """
        if not config.model_name:
            return False
        if config.temperature < 0.0 or config.temperature > 2.0:
            return False
        return config.max_tokens is None or config.max_tokens > 0

    def estimate_cost(self, tokens: int) -> float:
        """
        Estimate cost for a given number of tokens.

        Args:
            tokens: Number of tokens

        Returns:
            Estimated cost in USD
        """
        # Override in subclasses for provider-specific pricing
        return 0.0
