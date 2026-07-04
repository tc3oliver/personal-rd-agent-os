"""Citation validator — checks chunk exists, hash matches, and is in retrieved context."""

from __future__ import annotations

from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.schemas.citation import (
    Citation,
    CitationReport,
    CitationValidationResult,
)
from rdos.schemas.document import DocumentChunk


class CitationValidator:
    """Validate citations against the local store + retrieved context."""

    def __init__(self, store: SqliteMetadataStore) -> None:
        self.store = store

    def validate(
        self,
        citation: Citation,
        retrieved_chunks: list[DocumentChunk],
    ) -> CitationValidationResult:
        chunk = self.store.get_chunk(citation.chunk_id)

        chunk_exists = chunk is not None
        hash_matches = bool(chunk) and chunk.chunk_hash == citation.chunk_hash

        retrieved_ids = {c.chunk_id for c in retrieved_chunks}
        in_retrieved = citation.chunk_id in retrieved_ids

        error: str | None = None
        if not chunk_exists:
            error = "chunk_id not found in store"
        elif not hash_matches:
            error = "chunk_hash mismatch"
        elif not in_retrieved:
            error = "citation not in retrieved context"

        return CitationValidationResult(
            citation=citation,
            chunk_exists=chunk_exists,
            hash_matches=hash_matches,
            in_retrieved_context=in_retrieved,
            error=error,
        )

    def validate_many(
        self,
        citations: list[Citation],
        retrieved_chunks: list[DocumentChunk],
    ) -> CitationReport:
        results = [self.validate(c, retrieved_chunks) for c in citations]
        return CitationReport(results=results)
