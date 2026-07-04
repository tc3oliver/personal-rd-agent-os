"""Hybrid search: merges semantic + keyword results via RRF.

Pure function; stateful stores are passed in. Returned chunks are
annotated with a unified score in [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass

from rdos.schemas.document import DocumentChunk
from rdos.schemas.privacy import PrivacyLevel


@dataclass
class RetrievalFilters:
    privacy_levels: list[PrivacyLevel] | None = None
    tags: list[str] | None = None
    folder: str | None = None
    date_from: str | None = None
    date_to: str | None = None


def _matches_filters(chunk: DocumentChunk, f: RetrievalFilters) -> bool:
    if f.privacy_levels and chunk.privacy_level not in f.privacy_levels:
        return False
    if f.tags:
        if not set(chunk.tags).intersection(f.tags):
            return False
    if f.folder:
        if f.folder not in chunk.file_path:
            return False
    if f.date_from and chunk.date and chunk.date < f.date_from:
        return False
    if f.date_to and chunk.date and chunk.date > f.date_to:
        return False
    return True


def reciprocal_rank_fusion(
    semantic: list[tuple[str, float]],
    keyword: list[tuple[str, float]],
    *,
    k: int = 60,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> dict[str, float]:
    """Merge two ranked lists into a unified score via RRF.

    `semantic` and `keyword` are list[(chunk_id, raw_score)]. raw_score is
    ignored — only rank matters in classic RRF.
    """
    scores: dict[str, float] = {}
    for rank, (chunk_id, _raw) in enumerate(semantic):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + semantic_weight / (k + rank + 1)
    for rank, (chunk_id, _raw) in enumerate(keyword):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + keyword_weight / (k + rank + 1)
    return scores
