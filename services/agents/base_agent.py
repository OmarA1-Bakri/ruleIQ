"""Base agent class for all agent personas."""

from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime, timezone


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, agent_id: str, session_id: str, user_id: str) -> None:
        """Initialize base agent."""
        self.agent_id = agent_id
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now(timezone.utc)
        self.trust_level = 0

    @abstractmethod
    def validate_capabilities(self, action_type: str) -> bool:
        """Validate if agent can perform action."""
        pass

    @abstractmethod
    async def suggest_action(
        self, action_type: str, description: str, rationale: str, **kwargs
    ) -> Any:
        """Suggest an action for approval."""
        pass
