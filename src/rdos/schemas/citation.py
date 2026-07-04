"""Citation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A reference from an answer back to a source chunk."""

    chunk_id: str
    doc_id: str
    file_path: str
    title: str
    heading_path: list[str] = Field(default_factory=list)
    quote: str
    chunk_hash: str
    score: float | None = None


class CitationValidationResult(BaseModel):
    """Outcome of validating a single citation."""

    citation: Citation
    chunk_exists: bool
    hash_matches: bool
    in_retrieved_context: bool

    @property
    def is_valid(self) -> bool:
        return self.chunk_exists and self.hash_matches and self.in_retrieved_context

    error: str | None = None


class CitationReport(BaseModel):
    """Aggregate result for a list of citations."""

    results: list[CitationValidationResult] = Field(default_factory=list)

    @property
    def all_valid(self) -> bool:
        return all(r.is_valid for r in self.results)

    @property
    def valid_count(self) -> int:
        return sum(1 for r in self.results if r.is_valid)

    @property
    def total_count(self) -> int:
        return len(self.results)
