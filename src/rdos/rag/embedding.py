"""Embedding provider abstraction.

Batch 0 ships only the interface and a deterministic fake implementation.
Later batches swap in a real provider (local bge-m3 or OpenAI) via config.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class EmbeddingProvider(Protocol):
    """Embedding provider contract.

    Implementations MUST be deterministic for the same input text so that
    index ↔ query embeddings stay comparable.
    """

    @property
    def dim(self) -> int:
        """Return embedding dimensionality."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per input."""
        ...

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text. Default implementation uses `embed`."""
        return self.embed([text])[0]


class FakeEmbeddingProvider:
    """Deterministic hash-based fake embedding.

    - Vector is derived from a stable SHA256 hash of the input text.
    - Same text → same vector always.
    - dim is configurable (default 1024 to match local bge-m3 setup).

    NOT semantically meaningful — only used for plumbing until the real
    embedding provider is wired in (Batch 3, post-stabilization).
    """

    def __init__(self, dim: int = 1024) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # Expand hash to cover dim bytes by re-hashing in a chain.
            buf = bytearray(h)
            counter = 0
            while len(buf) < self._dim:
                counter += 1
                buf += hashlib.sha256(h + counter.to_bytes(4, "big")).digest()
            arr = np.frombuffer(bytes(buf[: self._dim]), dtype=np.uint8).astype(np.float32)
            # Map to [-1, 1] and normalize to unit length.
            arr = (arr / 127.5) - 1.0
            norm = float(np.linalg.norm(arr)) or 1.0
            out.append((arr / norm).tolist())
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


def build_embedding_provider(provider: str, dim: int = 1024, **_kwargs: object) -> EmbeddingProvider:
    """Factory. Later batches extend this with `local` and `openai`."""
    if provider == "fake":
        return FakeEmbeddingProvider(dim=dim)
    raise ValueError(f"Unknown embedding provider: {provider!r}")
