"""Document and chunk schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rdos.schemas.privacy import PrivacyLevel


class DocumentMetadata(BaseModel):
    """Document-level metadata, derived from frontmatter + path."""

    doc_id: str
    file_path: str
    title: str
    date: str | None = None
    tags: list[str] = Field(default_factory=list)
    privacy_level: PrivacyLevel = PrivacyLevel.private_raw
    content_hash: str
    indexed_at: str | None = None
    # Batch 12: corpus provenance
    source_collection: str = ""
    topic: str = ""
    stale: bool = False
    last_modified: float | None = None


class DocumentChunk(BaseModel):
    """A heading-aware chunk produced by the chunker."""

    doc_id: str
    file_path: str
    title: str
    heading_path: list[str] = Field(default_factory=list)
    chunk_id: str
    chunk_text: str
    token_count: int
    content_hash: str   # hash of full document text
    chunk_hash: str     # hash of (chunk_text + key metadata)
    privacy_level: PrivacyLevel = PrivacyLevel.private_raw
    tags: list[str] = Field(default_factory=list)
    date: str | None = None
    # Batch 12: corpus provenance (propagated from parent doc)
    source_collection: str = ""
    topic: str = ""

    # Filled by retriever
    score: float | None = None
