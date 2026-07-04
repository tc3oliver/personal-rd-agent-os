"""Research answer schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rdos.schemas.citation import Citation
from rdos.schemas.privacy import PrivacyLevel


class ResearchAnswer(BaseModel):
    """Final structured answer returned by the research_memory_graph."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    selected_model_profile: str
    effective_privacy_level: PrivacyLevel
    task_type: str = "research_memory"

    # Populated by structured-output formatter
    structured_payload: dict | None = None
