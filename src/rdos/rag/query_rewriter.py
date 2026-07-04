"""Query rewriter — preserve English technical terms, expand aliases.

Real corpus queries mix Traditional Chinese with English technical
proper nouns (GraphRAG, AgentTrace, RAG). Naive keyword search treats
the whole query as a single token stream, which hurts recall.

Strategy:
1. Pull ASCII / alphanumeric runs out as-is (technical terms preserved).
2. Split CJK text into character n-gram windows for partial matching.
3. Apply alias expansion from configs/rag.yaml.

This is intentionally a heuristic, not a learned model. It runs offline,
fails safe, and the rewrite is logged in trace so the eval harness can
score it.
"""

from __future__ import annotations

import re
from typing import Any

from rdos.config import RagConfig  # noqa: F401  (used in type hint)

_ASCII_RUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-+.]*")
_CJK_RUN_RE = re.compile(r"[　-鿿]+")


def _default_aliases() -> dict[str, list[str]]:
    return {
        "agenttrace": ["agent trace", "flight recorder", "agent flight recorder"],
        "graphrag": ["graph rag", "層次化摘要", "層次化", "hierarchical summary"],
        "vectorrag": ["vector rag", "dense retrieval"],
        "argus": ["argus-llm", "argus llm", "g-arvis", "六維度評估"],
        "contextengineering": ["context engineering", "記憶與檢索"],
        "rag": ["retrieval augmented generation", "檢索增強生成"],
        "mka": ["memory keyed attention"],
        "bor": ["bits over random"],
        "mnemosyne": ["semantic code retrieval"],
    }


def _normalize_alias_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _load_aliases_from_config(cfg: Any) -> dict[str, list[str]]:
    raw = getattr(cfg, "query_rewrite_aliases", None) or {}
    out: dict[str, list[str]] = {}
    for key, vals in raw.items():
        norm = _normalize_alias_key(str(key))
        if norm:
            out[norm] = [str(v) for v in vals]
    return out


def rewrite_query(query: str, cfg: RagConfig | None = None) -> dict[str, Any]:
    """Return {'original': str, 'tokens': [...], 'rewritten_queries': [...]}."""
    base_aliases = _default_aliases()
    if cfg is not None:
        base_aliases.update(_load_aliases_from_config(cfg))

    ascii_tokens: list[str] = []
    for m in _ASCII_RUN_RE.finditer(query):
        tok = m.group(0)
        if len(tok) >= 2:
            ascii_tokens.append(tok)

    cjk_tokens: list[str] = []
    for m in _CJK_RUN_RE.finditer(query):
        text = m.group(0).strip()
        # Split CJK into 2-char and 3-char windows for fuzzier matching
        if not text:
            continue
        cjk_tokens.append(text)
        if len(text) >= 3:
            for i in range(len(text) - 1):
                cjk_tokens.append(text[i : i + 2])

    base_tokens = ascii_tokens + cjk_tokens

    # Alias expansion: for each ascii token, see if it maps.
    expansions: list[str] = []
    for tok in ascii_tokens:
        norm = _normalize_alias_key(tok)
        for alias in base_aliases.get(norm, []):
            expansions.append(alias)

    rewritten_queries: list[str] = []
    if expansions:
        rewritten_queries.append(" ".join(base_tokens + expansions))
    rewritten_queries.append(" ".join(base_tokens))
    if ascii_tokens:
        rewritten_queries.append(" ".join(ascii_tokens))

    return {
        "original": query,
        "tokens": base_tokens,
        "ascii_tokens": ascii_tokens,
        "cjk_tokens": cjk_tokens,
        "alias_expansions": expansions,
        "rewritten_queries": rewritten_queries,
    }
