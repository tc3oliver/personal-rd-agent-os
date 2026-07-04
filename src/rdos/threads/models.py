"""Thread schema — persistent conversation state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TurnRecord(BaseModel):
    """One ask/answer turn inside a thread."""

    turn_index: int
    run_id: str
    question: str
    answer: str = ""
    citation_chunk_ids: list[str] = Field(default_factory=list)
    timestamp: str


class ThreadState(BaseModel):
    """A research thread — persistent across multiple `rdos thread ask`."""

    thread_id: str
    created_at: str
    closed_at: str | None = None
    turns: list[TurnRecord] = Field(default_factory=list)
    cited_chunks: list[str] = Field(default_factory=list)  # carry-forward chunk_ids
    compressed_summary: str = ""
    privacy_level: str = "private_raw"
    source_collection: str = ""
