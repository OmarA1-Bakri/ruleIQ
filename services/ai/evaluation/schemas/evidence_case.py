#!/usr/bin/env python3
"""Evidence case schemas for Golden Dataset system."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from .common import RegCitation, SourceMeta, TemporalValidity


class EvidenceItem(BaseModel):
    """Required evidence item specification."""

    name: str = Field(..., description="Name of the evidence")
    kind: str = Field(
        ...,
        description="Type of evidence (e.g., document, log, certificate)",
    )
    acceptance_criteria: List[str] = Field(
        ...,
        description="Criteria for accepting this evidence",
    )
    example_locator: Optional[str] = Field(
        None,
        description="Example location (e.g., S3 path)",
    )


class FrameworkMap(BaseModel):
    """Mapping to control frameworks."""

    framework: str = Field(..., description="Framework name (e.g., NIST, ISO27001)")
    control_id: str = Field(..., description="Control ID within the framework")


class EvidenceCase(BaseModel):
    """Evidence case definition."""

    id: str = Field(..., description="Unique case identifier")
    title: str = Field(..., description="Case title")
    obligation_id: str = Field(..., description="Related obligation ID")
    required_evidence: List[EvidenceItem] = Field(
        ...,
        description="Required evidence items",
    )
    control_mappings: Optional[List[FrameworkMap]] = Field(
        None,
        description="Control framework mappings",
    )
    regulation_refs: List[RegCitation] = Field(
        default_factory=list,
        description="Regulatory references",
    )
    temporal: TemporalValidity = Field(..., description="Temporal validity")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    version: str = Field(..., description="Version of the case")
    source: SourceMeta = Field(..., description="Source metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
