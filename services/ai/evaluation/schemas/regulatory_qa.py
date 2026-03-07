#!/usr/bin/env python3
"""Regulatory Q&A pair schemas for Golden Dataset system."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from .common import RegCitation, SourceMeta, TemporalValidity


class RegulatoryQAPair(BaseModel):
    """Regulatory Q&A pair definition."""

    id: str = Field(..., description="Unique Q&A identifier")
    question: str = Field(..., description="The regulatory question")
    authoritative_answer: str = Field(..., description="The authoritative answer")
    regulation_refs: List[RegCitation] = Field(..., description="Regulatory references")
    temporal: TemporalValidity = Field(..., description="Temporal validity")
    topic: Optional[str] = Field(None, description="Topic category")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    version: str = Field(..., description="Version of the Q&A pair")
    source: SourceMeta = Field(..., description="Source metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
