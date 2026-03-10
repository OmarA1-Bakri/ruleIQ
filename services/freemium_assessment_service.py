"""
FreemiumAssessmentService - Backward-compatible facade.

This module re-exports from the services.freemium_assessment package
so that existing imports continue to work.
"""

from services.freemium_assessment import FreemiumAssessmentService

__all__ = ["FreemiumAssessmentService"]
