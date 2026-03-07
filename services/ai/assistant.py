"""
Backward-compatibility shim for services.ai.assistant

The ComplianceAssistant class was refactored into services.ai.assistant_facade
as part of the modular architecture migration. This module re-exports it
so that existing imports (25+ files) continue to work.

For new code, prefer: from services.ai import ComplianceAssistant
"""

from .assistant_facade import ComplianceAssistant

__all__ = ["ComplianceAssistant"]
