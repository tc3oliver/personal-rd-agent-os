"""Tests for Pydantic schemas."""

from __future__ import annotations

from rdos.schemas import (  # noqa: F401  (import side-effect rebuilds forward refs)
    Citation,
    CitationReport,
    CitationValidationResult,
    DocumentChunk,
    PrivacyDecision,
    PrivacyLevel,
    ResearchAnswer,
    TraceRecord,
    privacy_max,
    privacy_rank,
)


def test_privacy_order_rank() -> None:
    assert privacy_rank(PrivacyLevel.public) < privacy_rank(PrivacyLevel.private_summary)
    assert privacy_rank(PrivacyLevel.private_summary) < privacy_rank(PrivacyLevel.private_raw)
    assert privacy_rank(PrivacyLevel.private_raw) < privacy_rank(PrivacyLevel.company_sensitive)


def test_privacy_max_takes_strictest() -> None:
    assert privacy_max([PrivacyLevel.public, PrivacyLevel.company_sensitive]) == PrivacyLevel.company_sensitive
    assert privacy_max([PrivacyLevel.private_raw, PrivacyLevel.public]) == PrivacyLevel.private_raw
    assert privacy_max([]) == PrivacyLevel.public


def test_document_chunk_defaults() -> None:
    chunk = DocumentChunk(
        doc_id="d1",
        file_path="x.md",
        title="X",
        heading_path=["H1", "H2"],
        chunk_id="c1",
        chunk_text="hello",
        token_count=2,
        content_hash="hash-full",
        chunk_hash="hash-chunk",
    )
    assert chunk.privacy_level == PrivacyLevel.private_raw
    assert chunk.tags == []


def test_citation_validation_aggregate() -> None:
    cit = Citation(
        chunk_id="c1",
        doc_id="d1",
        file_path="x.md",
        title="X",
        heading_path=["H"],
        quote="...",
        chunk_hash="h",
    )
    valid = CitationValidationResult(
        citation=cit,
        chunk_exists=True,
        hash_matches=True,
        in_retrieved_context=True,
    )
    invalid = CitationValidationResult(
        citation=cit,
        chunk_exists=True,
        hash_matches=False,
        in_retrieved_context=True,
    )
    report = CitationReport(results=[valid, invalid])
    assert report.total_count == 2
    assert report.valid_count == 1
    assert report.all_valid is False


def test_research_answer_roundtrip() -> None:
    ans = ResearchAnswer(
        answer="yes",
        citations=[],
        confidence=0.7,
        selected_model_profile="local_fast",
        effective_privacy_level=PrivacyLevel.private_raw,
    )
    dumped = ans.model_dump()
    restored = ResearchAnswer(**dumped)
    assert restored == ans


def test_trace_record_minimal() -> None:
    rec = TraceRecord(
        run_id="r1",
        timestamp="2026-07-05T00:00:00Z",
        task_type="research_memory",
        user_query="q",
    )
    assert rec.errors == []
    assert rec.metrics.latency_ms is None


def test_privacy_decision_fields() -> None:
    pd = PrivacyDecision(
        user_query_privacy=PrivacyLevel.private_summary,
        retrieved_chunk_privacies=[PrivacyLevel.private_raw],
        effective_privacy_level=PrivacyLevel.private_raw,
        allows_external_model=False,
        requires_user_confirmation=False,
        reason="private_raw chunks retrieved",
    )
    assert pd.effective_privacy_level == PrivacyLevel.private_raw
    assert pd.allows_external_model is False
