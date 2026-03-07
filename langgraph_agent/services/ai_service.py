"""

AI Service wrapper for LangGraph integration.
Bridges to existing AI assistant service.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from services.ai.assistant import ComplianceAssistant as AIAssistant
from typing import Optional, Dict, Any


class AIService:
    """Wrapper for AI service integration."""

    def __init__(self) -> None:
        """Initialize AI service with existing assistant."""
        self.assistant = None

    async def initialize(self) -> None:
        """Async initialization of AI assistant."""
        if not self.assistant:
            self.assistant = AIAssistant()
            await self.assistant.initialize()

    async def generate_response(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate AI response using the assistant."""
        if not self.assistant:
            await self.initialize()
        response = await self.assistant.generate(
            prompt=prompt, context=context or {}, temperature=0.7
        )
        return response.content if hasattr(response, "content") else str(response)

    async def close(self) -> None:
        """Clean up resources."""
        if self.assistant:
            await self.assistant.cleanup()
