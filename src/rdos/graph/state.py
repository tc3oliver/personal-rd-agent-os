"""LangGraph state for the research_memory workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from rdos.schemas.citation import Citation, CitationReport
from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyDecision, PrivacyLevel
from rdos.schemas.research import ResearchAnswer
from rdos.schemas.routing import ModelRoutingDecision


class ResearchGraphState(TypedDict, total=False):
    # Input
    user_query: str
    task_type: str  # first version: always "research_memory"

    # Privacy
    query_privacy_level: PrivacyLevel
    privacy_decision: PrivacyDecision
    effective_privacy_level: PrivacyLevel

    # Retrieval
    retrieved_chunks: list[DocumentChunk]
    retrieved_doc_ids: list[str]

    # Routing
    model_routing: ModelRoutingDecision

    # Context + raw generation
    context: str
    raw_answer: str

    # Citation
    citations: list[Citation]
    citation_report: CitationReport

    # Final output
    final_answer: ResearchAnswer
    structured_payload: dict[str, Any]

    # Diagnostics
    confidence: float
    errors: list[str]
