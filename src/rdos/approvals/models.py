"""Approval request schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    """One approval request, persisted in SQLite."""

    approval_id: str
    run_id: str
    thread_id: str
    tool_name: str
    args: dict = Field(default_factory=dict)
    requested_at: str  # ISO 8601
    decided_at: str | None = None
    decision: str | None = None  # "approved" | "denied" | None
    decided_by: str | None = None
    deny_reason: str | None = None
    idempotency_key: str
    replay_count: int = 0
