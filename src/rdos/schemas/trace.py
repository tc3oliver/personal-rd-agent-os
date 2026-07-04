"""Trace schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rdos.schemas.citation import Citation, CitationReport
from rdos.schemas.privacy import PrivacyDecision
from rdos.schemas.research import ResearchAnswer
from rdos.schemas.routing import ModelRoutingDecision


class TraceMetrics(BaseModel):
    """Per-run metrics."""

    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    retrieval_count: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TraceError(BaseModel):
    """Error captured during a run."""

    code: str
    message: str
    node: str | None = None
    traceback: str | None = None


class TraceRecord(BaseModel):
    """One JSONL trace entry. Written by TraceStore on every run."""

    run_id: str
    timestamp: str  # ISO 8601
    task_type: str
    user_query: str

    privacy_decision: PrivacyDecision | None = None
    effective_privacy_level: str | None = None

    model_routing_decision: ModelRoutingDecision | None = None

    retrieved_doc_ids: list[str] = Field(default_factory=list)
    retrieved_chunks: list[dict] = Field(default_factory=list)

    citations: list[Citation] = Field(default_factory=list)
    citation_report: CitationReport | None = None

    final_answer: ResearchAnswer | None = None
    structured_output: dict | None = None

    metrics: TraceMetrics = Field(default_factory=TraceMetrics)
    errors: list[TraceError] = Field(default_factory=list)
