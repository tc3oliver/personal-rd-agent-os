"""Corpus presets — folder scopes for known research libraries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CorpusPreset:
    name: str
    description: str
    folders: tuple[str, ...]


_RESEARCH_NOTE_SCOPES = {
    "rag": CorpusPreset(
        "rag", "知識與檢索", ("知識與檢索",)
    ),
    "agent": CorpusPreset(
        "agent", "AI代理系統", ("AI代理系統",)
    ),
    "eval": CorpusPreset(
        "eval", "LLM推理與評估", ("LLM推理與評估",)
    ),
    "security": CorpusPreset(
        "security", "AI安全", ("AI安全",)
    ),
    "devtools": CorpusPreset(
        "devtools", "開發者工具與框架", ("開發者工具與框架",)
    ),
    "all": CorpusPreset(
        "all", "全部主題", ()
    ),
}


CORPUS_PRESETS: dict[str, dict[str, CorpusPreset]] = {
    "research-notes": _RESEARCH_NOTE_SCOPES,
    # Backward-compatible alias for the original private validation corpus.
    "clawd-research": _RESEARCH_NOTE_SCOPES,
}


def get_preset(corpus: str, scope: str) -> CorpusPreset:
    if corpus not in CORPUS_PRESETS:
        raise ValueError(
            f"unknown corpus: {corpus!r}; known: {sorted(CORPUS_PRESETS)}"
        )
    scopes = CORPUS_PRESETS[corpus]
    if scope not in scopes:
        raise ValueError(
            f"unknown scope: {scope!r} for corpus {corpus!r}; "
            f"known: {sorted(scopes)}"
        )
    return scopes[scope]


def resolve_corpus_root(corpus: str) -> str:
    """Map corpus name → filesystem root.

    Overridable via env var RDOS_CORPUS_<NAME>_ROOT so users don't have to
    pass the path every time. Defaults avoid private machine-specific paths.
    """
    import os

    env_var = f"RDOS_CORPUS_{corpus.upper().replace('-', '_')}_ROOT"
    override = os.environ.get(env_var)
    if override:
        return override
    home = os.path.expanduser("~")
    defaults = {
        "research-notes": f"{home}/research-notes",
        "clawd-research": f"{home}/research-notes",
    }
    if corpus not in defaults:
        raise ValueError(f"unknown corpus: {corpus!r}")
    return defaults[corpus]
