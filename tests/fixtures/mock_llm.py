"""

Mock LLM for deterministic testing in LangGraph workflows.

Provides consistent, predictable responses for testing without API calls.
"""

from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.outputs import LLMResult, Generation
from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import CallbackManagerForLLMRun
import json


class MockLLM(BaseChatModel):
    """
    Deterministic mock LLM for testing.

    Provides predictable responses based on input patterns.
    Temperature is always 0 for deterministic outputs.
    """

    # Class attributes for LangChain compatibility
    temperature: float = 0.0
    model_name: str = "mock-llm"

    def __init__(self, responses: Optional[Dict[str, str]] = None, **kwargs):
        """
        Initialize mock LLM with optional response mappings.

        Args:
            responses: Dict mapping input patterns to responses
        """
        super().__init__(**kwargs)
        self.responses = responses or self._get_default_responses()
        self.call_history: List[Dict[str, Any]] = []

    def _get_default_responses(self) -> Dict[str, str]:
        """Get default response mappings for common patterns."""
        return {
            # Compliance-related patterns
            "compliance": json.dumps(
                {
                    "assessment": "compliant",
                    "confidence": 0.95,
                    "evidence": ["Document reviewed", "Controls validated"],
                },
            ),
            # Risk assessment patterns
            "risk": json.dumps(
                {
                    "level": "medium",
                    "factors": ["Data exposure", "Third-party dependencies"],
                    "mitigation": "Implement additional controls",
                },
            ),
            # State transition patterns
            "next_step": "data_collection",
            "transition": "approved",
            # Generic patterns
            "test": "Test response for validation",
            "error": "Error simulation response",
            # JSON response pattern
            "json": json.dumps({"status": "success", "data": "test"}),
            # Workflow decisions
            "decision": "proceed",
            "validation": "valid",
            # Data processing
            "extract": json.dumps(
                {
                    "entities": ["Entity1", "Entity2"],
                    "relationships": [
                        {"from": "Entity1", "to": "Entity2", "type": "relates_to"},
                    ],
                },
            ),
        }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """
        Generate response based on input messages.

        Synchronous version for LangChain compatibility.
        """
        # Extract the last user message
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, (HumanMessage, str)):
                user_message = str(msg.content if hasattr(msg, "content") else msg)
                break

        # Record the call
        self.call_history.append(
            {
                "timestamp": "2025-08-27T00:00:00Z",
                "messages": [
                    {
                        "role": m.__class__.__name__,
                        "content": str(m.content if hasattr(m, "content") else m),
                    }
                    for m in messages
                ],
                "kwargs": kwargs,
            },
        )

        # Find matching response pattern
        response = self._get_response_for_input(user_message.lower())

        # Create generation
        generation = Generation(
            text=response,
            generation_info={"mock": True, "pattern_matched": True},
        )

        return LLMResult(generations=[[generation]])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """
        Async version of generate for LangChain compatibility.
        """
        # Simply call the sync version as this is a mock
        return self._generate(messages, stop, run_manager, **kwargs)

    def _get_response_for_input(self, input_text: str) -> str:
        """
        Get response based on input text patterns.

        Args:
            input_text: Lowercase input text to match against patterns

        Returns:
            Matched response or default response
        """
        # Check for exact matches first
        if input_text in self.responses:
            return self.responses[input_text]

        # Check for pattern matches
        for pattern, response in self.responses.items():
            if pattern in input_text:
                return response

        # Default structured response
        return json.dumps(
            {
                "response": "Default mock response",
                "confidence": 0.8,
                "metadata": {"mock": True},
            },
        )

    def add_response(self, pattern: str, response: str):
        """
        Add a custom response pattern for testing.

        Args:
            pattern: Input pattern to match (will be lowercased)
            response: Response to return for this pattern
        """
        self.responses[pattern.lower()] = response

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get the history of all calls made to this mock."""
        return self.call_history

    def reset_history(self):
        """Reset the call history."""
        self.call_history = []

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM."""
        return "mock"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return parameters for identifying this LLM."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "mock": True,
        }


class MockLLMWithStreaming(MockLLM):
    """Mock LLM with streaming support for testing streaming workflows."""

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ):
        """Stream tokens for testing streaming functionality."""
        response = self._get_response_for_input(
            str(messages[-1].content if messages else ""),
        )

        # Simulate streaming by yielding response in chunks
        words = response.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ):
        """Async stream tokens for testing streaming functionality."""
        response = self._get_response_for_input(
            str(messages[-1].content if messages else ""),
        )

        # Simulate streaming by yielding response in chunks
        words = response.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word


def create_deterministic_llm(scenario: str = "default") -> MockLLM:
    """
    Factory function to create mock LLMs for specific test scenarios.

    Args:
        scenario: Test scenario name

    Returns:
        Configured MockLLM instance
    """
    scenarios = {
        "default": {},
        "compliance_assessment": {
            "assess": json.dumps(
                {
                    "compliant": True,
                    "gaps": [],
                    "recommendations": ["Continue monitoring"],
                    "confidence": 0.98,
                },
            ),
            "validate": json.dumps({"valid": True, "issues": []}),
        },
        "error_simulation": {
            "process": "ERROR: Simulated failure",
            "validate": json.dumps(
                {"valid": False, "errors": ["Invalid input", "Missing data"]},
            ),
        },
        "state_transitions": {
            "next": "review",
            "decide": "approve",
            "route": "human_review",
        },
        "data_extraction": {
            "extract": json.dumps(
                {
                    "controls": [
                        {"id": "CTRL-001", "name": "Access Control"},
                        {"id": "CTRL-002", "name": "Data Encryption"},
                    ],
                    "obligations": [
                        {
                            "id": "OBL-001",
                            "regulation": "GDPR",
                            "requirement": "Data protection",
                        },
                    ],
                },
            ),
        },
    }

    responses = scenarios.get(scenario, {})
    return MockLLM(responses=responses)


# Fixture function for pytest
def mock_llm_fixture():
    """Pytest fixture for mock LLM."""
    return create_deterministic_llm("default")


# Factory function for creating mock LLMs
def mock_llm_factory(scenario: str = "default"):
    """Factory function for creating mock LLMs with different scenarios."""
    return create_deterministic_llm(scenario)
