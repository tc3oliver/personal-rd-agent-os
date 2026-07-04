"""Embedding provider abstraction.

Two providers ship today:
- FakeEmbeddingProvider: deterministic hash-based, for tests / offline CI
- OpenAICompatibleEmbeddingProvider: real local bge-m3 (or any OpenAI-compatible /v1/embeddings endpoint)

Provider selection is by name via build_embedding_provider(name).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Protocol

import requests


class EmbeddingProvider(Protocol):
    """Embedding provider contract.

    Implementations MUST be deterministic for the same input text so that
    index ↔ query embeddings stay comparable.
    """

    @property
    def name(self) -> str:
        """Stable identifier persisted in LanceDB metadata."""
        ...

    @property
    def model(self) -> str:
        """Underlying model name (e.g. 'bge-m3-q8_0', 'fake')."""
        ...

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
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake"

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        out: list[list[float]] = []
        for text in texts:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            buf = bytearray(h)
            counter = 0
            while len(buf) < self._dim:
                counter += 1
                buf += hashlib.sha256(h + counter.to_bytes(4, "big")).digest()
            arr = np.frombuffer(bytes(buf[: self._dim]), dtype=np.uint8).astype(np.float32)
            arr = (arr / 127.5) - 1.0
            norm = float(np.linalg.norm(arr)) or 1.0
            out.append((arr / norm).tolist())
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@dataclass
class OpenAICompatibleEmbeddingConfig:
    name: str
    base_url: str
    model: str
    dim: int
    api_key_env: str = "RDOS_LOCAL_MODEL_API_KEY"
    timeout: float = 60.0
    batch_size: int = 32


class OpenAICompatibleEmbeddingProvider:
    """OpenAI-compatible /v1/embeddings client (llama.cpp, Ollama, etc.).

    Supports batch input via `input: [...]`. Falls back gracefully on
    connection errors — caller decides whether to retry or fail hard.
    """

    def __init__(self, cfg: OpenAICompatibleEmbeddingConfig) -> None:
        self.cfg = cfg
        self._api_key = os.environ.get(cfg.api_key_env, "local-dev-key")

    @property
    def name(self) -> str:
        return self.cfg.name

    @property
    def model(self) -> str:
        return self.cfg.model

    @property
    def dim(self) -> int:
        return self.cfg.dim

    def health(self) -> bool:
        try:
            r = requests.get(
                f"{self.cfg.base_url.rstrip('/').removesuffix('/v1')}/health",
                timeout=self.cfg.timeout,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        base = self.cfg.base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = base + "/v1"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        for i in range(0, len(texts), self.cfg.batch_size):
            batch = texts[i : i + self.cfg.batch_size]
            r = requests.post(
                f"{base}/embeddings",
                headers=headers,
                json={"model": self.cfg.model, "input": batch},
                timeout=self.cfg.timeout,
            )
            r.raise_for_status()
            data = r.json()
            for obj in sorted(data["data"], key=lambda o: o.get("index", 0)):
                vec = obj["embedding"]
                if len(vec) != self.cfg.dim:
                    raise ValueError(
                        f"embedding dim mismatch: server returned {len(vec)}, "
                        f"expected {self.cfg.dim}"
                    )
                out.append([float(x) for x in vec])
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


# ----- factory -----


def build_embedding_provider(
    provider: str,
    dim: int = 1024,
    *,
    base_url: str | None = None,
    model: str | None = None,
    api_key_env: str | None = None,
    timeout: float = 60.0,
    batch_size: int = 32,
    **_kwargs: Any,
) -> EmbeddingProvider:
    """Build a provider by name.

    `provider` values we recognize:
    - "fake" → FakeEmbeddingProvider(dim)
    - "local-bge-m3" → OpenAICompatibleEmbeddingProvider against bge-m3 endpoint
    """
    if provider == "fake":
        return FakeEmbeddingProvider(dim=dim)
    if provider == "local-bge-m3":
        cfg = OpenAICompatibleEmbeddingConfig(
            name="local-bge-m3",
            base_url=base_url or os.environ.get(
                "RDOS_LOCAL_EMBEDDING_BASE_URL", "http://10.10.10.12:8081/v1"
            ),
            model=model or os.environ.get("RDOS_LOCAL_EMBEDDING_MODEL", "bge-m3-q8_0"),
            dim=int(os.environ.get("RDOS_LOCAL_EMBEDDING_DIM", dim)),
            api_key_env=api_key_env or "RDOS_LOCAL_MODEL_API_KEY",
            timeout=timeout,
            batch_size=batch_size,
        )
        return OpenAICompatibleEmbeddingProvider(cfg)
    raise ValueError(f"Unknown embedding provider: {provider!r}")
