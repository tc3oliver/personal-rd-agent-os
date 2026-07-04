"""LangGraph runtime — StateGraph implementation of the research_memory workflow.

Replaces the linear runner in Batch 14. Each node is a method that takes
state and returns a partial state update. The checkpointer (InMemorySaver
for dev/test) gives us thread_id-based persistence, which future HITL
features can build on.

The graph is compiled once and invoked per ask. Node-level timing and
status are captured into a trace buffer that the caller drains after invoke.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from rdos.config import RdosConfig
from rdos.graph.research_memory_graph import ResearchMemoryGraph
from rdos.graph.state import ResearchGraphState


class LangGraphRuntime:
    """Wrap a ResearchMemoryGraph in a LangGraph StateGraph."""

    def __init__(self, runner: ResearchMemoryGraph) -> None:
        self.runner = runner
        self.thread_id: str = ""
        self.node_trace: list[dict[str, Any]] = []
        self._compiled = self._build()

    def _build(self):
        # Each node delegates to the wrapped runner but records latency/status.
        runner = self.runner
        node_trace_ref = self.node_trace  # closure over the list

        def _wrap(name: str, fn: Callable[[ResearchGraphState], ResearchGraphState]):
            def node(state: ResearchGraphState) -> ResearchGraphState:
                started = time.perf_counter()
                in_summary = _summarize_state(state)
                try:
                    new_state = fn(state)
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    out_summary = _summarize_state(new_state)
                    node_trace_ref.append(
                        {
                            "name": name,
                            "status": "success",
                            "latency_ms": latency_ms,
                            "inputs_summary": in_summary,
                            "outputs_summary": out_summary,
                        }
                    )
                    # LangGraph TypedDict default reducer is "override"; return the
                    # full state so accumulated keys survive.
                    return new_state
                except Exception as exc:  # noqa: BLE001
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    node_trace_ref.append(
                        {
                            "name": name,
                            "status": "error",
                            "latency_ms": latency_ms,
                            "inputs_summary": in_summary,
                            "outputs_summary": {},
                            "error": str(exc)[:300],
                        }
                    )
                    raise

            return node

        builder = StateGraph(ResearchGraphState)
        builder.add_node("classify_task", _wrap("classify_task", runner.classify_task))
        builder.add_node("assess_query_privacy", _wrap("assess_query_privacy", runner.assess_query_privacy))
        builder.add_node("retrieve_notes", _wrap("retrieve_notes", runner.retrieve_notes))
        builder.add_node("calculate_effective_privacy", _wrap("calculate_effective_privacy", runner.calculate_effective_privacy))
        builder.add_node("select_model_profile", _wrap("select_model_profile", runner.select_model_profile))
        builder.add_node("build_context", _wrap("build_context", runner.build_context))
        builder.add_node("generate_answer", _wrap("generate_answer", runner.generate_answer))
        builder.add_node("build_citations", _wrap("build_citations", runner.build_citations))
        builder.add_node("validate_citations", _wrap("validate_citations", runner.validate_citations))
        builder.add_node("format_structured_output", _wrap("format_structured_output", runner.format_structured_output))

        builder.add_edge(START, "classify_task")
        builder.add_edge("classify_task", "assess_query_privacy")
        builder.add_edge("assess_query_privacy", "retrieve_notes")
        builder.add_edge("retrieve_notes", "calculate_effective_privacy")
        builder.add_edge("calculate_effective_privacy", "select_model_profile")
        builder.add_edge("select_model_profile", "build_context")
        builder.add_edge("build_context", "generate_answer")
        builder.add_edge("generate_answer", "build_citations")
        builder.add_edge("build_citations", "validate_citations")
        builder.add_edge("validate_citations", "format_structured_output")
        builder.add_edge("format_structured_output", END)

        checkpointer = InMemorySaver()
        return builder.compile(checkpointer=checkpointer)

    def invoke(self, user_query: str) -> tuple[ResearchGraphState, str]:
        self.thread_id = uuid.uuid4().hex
        # node_trace persists across invokes; reset on each entry.
        self.node_trace.clear()
        config = {"configurable": {"thread_id": self.thread_id}}
        result = self._compiled.invoke(
            {"user_query": user_query, "errors": []},
            config=config,
        )
        return result, self.thread_id


def _summarize_state(state: ResearchGraphState) -> dict[str, Any]:
    """Compact summary used in trace (avoid dumping full chunks)."""
    summary: dict[str, Any] = {}
    if "user_query" in state:
        summary["query_len"] = len(state.get("user_query", "") or "")
    if "retrieved_chunks" in state:
        chunks = state.get("retrieved_chunks") or []
        summary["retrieved_count"] = len(chunks)
    if "context" in state:
        summary["context_len"] = len(state.get("context", "") or "")
    if "raw_answer" in state:
        summary["answer_len"] = len(state.get("raw_answer", "") or "")
    if "effective_privacy_level" in state and state.get("effective_privacy_level"):
        summary["privacy"] = state["effective_privacy_level"].value
    if "citations" in state:
        summary["citation_count"] = len(state.get("citations") or [])
    return summary


def _diff(prev: ResearchGraphState, new: ResearchGraphState) -> dict[str, Any]:
    """Return only the keys that changed (LangGraph merges dicts)."""
    out: dict[str, Any] = {}
    for k, v in new.items():
        if prev.get(k) is not v and prev.get(k) != v:
            out[k] = v
    # Ensure user_query and errors survive the merge even if unchanged.
    out.setdefault("user_query", new.get("user_query", ""))
    out.setdefault("errors", new.get("errors", []))
    return out


def build_langgraph_runtime(
    *,
    config: RdosConfig | None = None,
    sqlite_store: Any = None,
    vector_store: Any = None,
    embedding: Any = None,
    llm: Any = None,
) -> LangGraphRuntime:
    """Build a LangGraph runtime with sensible defaults from config."""
    from rdos.config import get_config
    from rdos.rag.embedding import build_embedding_provider
    from rdos.rag.storage_sqlite import SqliteMetadataStore
    from rdos.rag.vector_store import LanceVectorStore

    cfg = config or get_config()
    store = sqlite_store or SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = vector_store or LanceVectorStore(
        cfg.rag.storage.lancedb_path,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    emb = embedding or build_embedding_provider(
        provider=cfg.models.embedding.provider,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    runner = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=llm
    )
    return LangGraphRuntime(runner)
