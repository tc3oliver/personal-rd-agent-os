"""Follow-up query rewriter — resolve pronouns / deixis against thread history."""

from __future__ import annotations

import re
from typing import Any

from rdos.threads.models import ThreadState

_PRONOUNS = ("它", "他", "她", "這個", "這項", "上述", "上面", "剛剛", "前面那")
_TOPIC_HINT_RE = re.compile(r"(?:跟|與|和)\s*(.+?)\s*(?:有什麼|的|之間)")


def _last_topic_keyword(state: ThreadState) -> str:
    """Pull the most recent technical proper-noun from prior questions."""
    for turn in reversed(state.turns):
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", turn.question):
            if tok.lower() not in {"the", "and", "for", "with", "what", "why", "how"}:
                return tok
    return ""


def rewrite_followup(state: ThreadState, query: str) -> str:
    """If query starts with a pronoun or lacks context, prepend last topic."""
    if not state.turns:
        return query
    last_topic = _last_topic_keyword(state)
    if not last_topic:
        return query
    q = query.strip()
    if any(q.startswith(p) for p in _PRONOUNS):
        return f"{last_topic} {q}"
    # Bare "可以舉例嗎？" → prepend topic
    if re.match(r"^(可以|能|請|有|是|怎樣|如何)", q) and last_topic not in q:
        return f"{last_topic} {q}"
    return q


def context_for_new_turn(state: ThreadState, *, max_turns: int = 5) -> dict[str, Any]:
    """Build a context dict the ask graph can merge into its prompt."""
    recent = state.turns[-max_turns:] if state.turns else []
    return {
        "prior_turns": [
            {
                "turn_index": t.turn_index,
                "question": t.question,
                "answer_excerpt": (t.answer or "")[:300],
                "citation_count": len(t.citation_chunk_ids),
            }
            for t in recent
        ],
        "cited_chunk_ids": list(state.cited_chunks),
        "compressed_summary": state.compressed_summary,
    }


def maybe_compress(state: ThreadState, *, max_turns: int = 5) -> bool:
    """If we exceed max_turns and have no summary yet, generate one.

    The 'summary' here is a deterministic concatenation of Q+A excerpts
    (LLM-driven compression is a follow-up). Returns True if a new
    summary was written.
    """
    if state.compressed_summary or len(state.turns) <= max_turns:
        return False
    parts: list[str] = []
    for t in state.turns[: -max_turns]:  # compress oldest
        parts.append(f"[T{t.turn_index}] Q: {t.question} | A: {(t.answer or '')[:200]}")
    state.compressed_summary = " || ".join(parts)[:2000]
    return True
