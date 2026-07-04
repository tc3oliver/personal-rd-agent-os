"""Schemas for the three real research apps."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rdos.schemas.citation import Citation


class DigestOutput(BaseModel):
    """rdos digest output."""

    date: str
    notes: list[dict] = Field(default_factory=list)
    clusters: list[dict] = Field(default_factory=list)
    suggested_ideas: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    privacy_level: str = "private_raw"


class TopicExplorerOutput(BaseModel):
    """rdos topic output."""

    topic: str
    representative_notes: list[dict] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    hot_keywords: list[str] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)
    suggested_outputs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class SynthesisClaim(BaseModel):
    """A single claim in a research synthesis."""

    statement: str
    citation_indices: list[int] = Field(default_factory=list)
    confidence: float = 0.5


class SynthesisOutput(BaseModel):
    """rdos synthesize output."""

    question: str
    summary: str = ""
    claims: list[SynthesisClaim] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    diverging_views: list[str] = Field(default_factory=list)
    actionable_for_rdos: list[str] = Field(default_factory=list)
    citation_coverage: float = 0.0  # fraction of claims backed by ≥1 citation
    privacy_level: str = "private_raw"
