"""
AI Services Module

This module provides AI-powered compliance assistance functionality.

## Architecture

The module has been refactored into a modular architecture:
- **Providers**: AI provider abstraction (Gemini, OpenAI, Anthropic)
- **Response**: Response generation, parsing, and formatting
- **Domains**: Domain-specific services (assessments, policies, workflows, etc.)

## Usage

### Legacy API (Recommended for existing code)
```python
from services.ai import ComplianceAssistant

assistant = ComplianceAssistant(db, user_context)
help_response = await assistant.get_assessment_help(...)
```

### New Modular API (For new code)
```python
from services.ai import AssessmentService, ProviderFactory

provider_factory = ProviderFactory(...)
assessment_service = AssessmentService(...)
help_response = await assessment_service.get_help(...)
```

## Migration

The `ComplianceAssistant` class is now a façade that delegates to the new
modular architecture. All existing code continues to work without changes.
New code should prefer using the domain services directly for better
testability and maintainability.
"""

# Import tool modules to trigger registration
from typing import Any, Dict, List, Optional
from . import assessment_tools, evidence_tools, regulation_tools  # noqa: F401

# Import assistant façade (maintains backward compatibility)
from .assistant_facade import ComplianceAssistant

# Import core tools functionality
from .tools import (
    BaseTool,
    ToolExecutor,
    ToolRegistry,
    ToolResult,
    ToolType,
    execute_tool,
    get_tool_schemas,
    register_tool,
    tool_executor,
    tool_registry,
)

# Import new architecture components (optional, for advanced users)
from .providers import (
    AIProvider,
    ProviderFactory,
    GeminiProvider,
    OpenAIProvider,
    AnthropicProvider,
)
from .response import ResponseGenerator, ResponseParser, FallbackGenerator
from .domains import (
    AssessmentService,
    PolicyService,
    WorkflowService,
    EvidenceService,
    ComplianceAnalysisService,
)

__all__ = [
    # Legacy API (façade)
    "ComplianceAssistant",
    # Tool system (existing)
    "BaseTool",
    "ToolExecutor",
    "ToolRegistry",
    "ToolResult",
    "ToolType",
    "execute_tool",
    "get_tool_schemas",
    "register_tool",
    "tool_executor",
    "tool_registry",
    # New architecture (optional, for advanced users)
    "AIProvider",
    "ProviderFactory",
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "ResponseGenerator",
    "ResponseParser",
    "FallbackGenerator",
    "AssessmentService",
    "PolicyService",
    "WorkflowService",
    "EvidenceService",
    "ComplianceAnalysisService",
]
