"""Pydantic schemas for RDOS."""

from rdos.schemas.citation import (
    Citation,
    CitationReport,
    CitationValidationResult,
)
from rdos.schemas.document import DocumentChunk, DocumentMetadata
from rdos.schemas.privacy import (
    PRIVACY_ORDER,
    PrivacyDecision,
    PrivacyLevel,
    privacy_max,
    privacy_rank,
)
from rdos.schemas.research import ResearchAnswer
from rdos.schemas.routing import ModelRoutingDecision
from rdos.schemas.trace import TraceError, TraceMetrics, TraceRecord

__all__ = [
    "Citation",
    "CitationReport",
    "CitationValidationResult",
    "DocumentChunk",
    "DocumentMetadata",
    "PRIVACY_ORDER",
    "PrivacyDecision",
    "PrivacyLevel",
    "ResearchAnswer",
    "ModelRoutingDecision",
    "TraceError",
    "TraceMetrics",
    "TraceRecord",
    "privacy_max",
    "privacy_rank",
]


# Force Pydantic to resolve forward references across schemas that reference
# each other (e.g. TraceRecord → CitationReport → Citation).
def _rebuild_all() -> None:
    from rdos.schemas.citation import CitationReport, CitationValidationResult  # noqa: F401
    from rdos.schemas.research import ResearchAnswer  # noqa: F401
    from rdos.schemas.trace import TraceRecord  # noqa: F401

    CitationReport.model_rebuild()
    CitationValidationResult.model_rebuild()
    ResearchAnswer.model_rebuild()
    TraceRecord.model_rebuild()


_rebuild_all()
