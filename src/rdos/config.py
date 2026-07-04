"""Config loader for RDOS.

Reads YAML configs from `configs/` and exposes typed views. Environment
variable substitution uses `${VAR}` syntax.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute_env(value: Any) -> Any:
    """Recursively replace ${VAR} with os.environ[VAR] (or '' if missing)."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    return _substitute_env(raw)


class ProfileConfig(BaseModel):
    provider: str
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    max_tokens: int = 4096
    temperature: float = 0.3
    allows_tools: bool = False
    description: str = ""


class EmbeddingConfig(BaseModel):
    provider: str = "fake"
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    dim: int = 1024


class ModelsConfig(BaseModel):
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    task_defaults: dict[str, str] = Field(default_factory=dict)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class PrivacyRule(BaseModel):
    allow_external_model: bool
    requires_user_confirmation: bool


class PrivacyPolicyConfig(BaseModel):
    privacy_order: list[str] = Field(default_factory=list)
    default_chunk_privacy: str = "private_raw"
    default_query_privacy: str = "private_raw"
    rules: dict[str, PrivacyRule] = Field(default_factory=dict)
    query_privacy_hints: dict[str, list[str]] = Field(default_factory=dict)


class ChunkingConfig(BaseModel):
    target_min_tokens: int = 300
    target_max_tokens: int = 600
    overlap_sentences: int = 1
    token_estimator: str = "char4"


class RetrievalConfig(BaseModel):
    top_k: int = 5
    semantic_weight: float = 0.6
    keyword_weight: float = 0.4
    min_score: float = 0.10
    rrf_k: int = 60


class EmbeddingRuntimeConfig(BaseModel):
    dim: int = 1024
    batch_size: int = 32


class StorageConfig(BaseModel):
    sqlite_path: str = "data/sqlite/rdos.db"
    lancedb_path: str = "data/lancedb"


class RagConfig(BaseModel):
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    embedding: EmbeddingRuntimeConfig = Field(default_factory=EmbeddingRuntimeConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


class ToolRule(BaseModel):
    description: str = ""
    allowed_privacy: list[str] = Field(default_factory=list)
    requires_confirmation: list[str] = Field(default_factory=list)
    blocked_privacy: list[str] = Field(default_factory=list)


class ToolPolicyConfig(BaseModel):
    default_policy: str = "deny"
    tools: dict[str, ToolRule] = Field(default_factory=dict)


class RdosConfig(BaseModel):
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    privacy_policy: PrivacyPolicyConfig = Field(default_factory=PrivacyPolicyConfig)
    rag: RagConfig = Field(default_factory=RagConfig)
    tool_policy: ToolPolicyConfig = Field(default_factory=ToolPolicyConfig)


def _default_configs_dir() -> Path:
    here = Path(__file__).resolve().parent
    # src/rdos/config.py → project root is 2 levels up from src/rdos/
    return here.parent.parent / "configs"


def load_config(configs_dir: Path | str | None = None) -> RdosConfig:
    """Load all configs from the given (or default) configs directory."""
    base = Path(configs_dir) if configs_dir else _default_configs_dir()

    raw_models = _load_yaml(base / "models.yaml")
    raw_privacy = _load_yaml(base / "privacy_policy.yaml")
    raw_rag = _load_yaml(base / "rag.yaml")
    raw_tools = _load_yaml(base / "tool_policy.yaml")

    return RdosConfig(
        models=ModelsConfig(**raw_models),
        privacy_policy=PrivacyPolicyConfig(**raw_privacy),
        rag=RagConfig(**raw_rag),
        tool_policy=ToolPolicyConfig(**raw_tools),
    )


@lru_cache(maxsize=1)
def get_config() -> RdosConfig:
    """Process-wide cached config."""
    return load_config()
