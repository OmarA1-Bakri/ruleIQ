#!/usr/bin/env python3
"""Compliance scenario schemas for Golden Dataset system."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from .common import RegCitation, SourceMeta, TemporalValidity, ExpectedOutcome


class ComplianceScenario(BaseModel):
    """Compliance scenario definition."""

    id: str = Field(..., description="Unique scenario identifier")
    title: str = Field(..., description="Scenario title")
    description: str = Field(..., description="Detailed scenario description")
    obligation_id: str = Field(..., description="Related obligation ID")
    sector: Optional[str] = Field(None, description="Industry sector")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction")
    regulation_refs: List[RegCitation] = Field(
        default_factory=list,
        description="Regulatory references",
    )
    triggers: List[str] = Field(..., description="Scenario triggers")
    expected_outcome: ExpectedOutcome = Field(
        ...,
        description="Expected compliance outcome",
    )
    temporal: TemporalValidity = Field(..., description="Temporal validity")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    version: str = Field(..., description="Version of the scenario")
    source: SourceMeta = Field(..., description="Source metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_validator("triggers")
    @classmethod
    def validate_triggers(cls, v: List[str]) -> List[str]:
        """Ensure triggers is not empty."""
        if not v:
            raise ValueError("triggers cannot be empty")
        return v

    @field_validator("expected_outcome")
    @classmethod
    def validate_outcome(cls, v: ExpectedOutcome) -> ExpectedOutcome:
        """Ensure outcome_code is present."""
        if not v.outcome_code or not v.outcome_code.strip():
            raise ValueError("outcome_code is required in expected_outcome")
        return v
