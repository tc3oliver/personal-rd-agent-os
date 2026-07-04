"""Research Memory Graph — 11-node LangGraph workflow.

Nodes:
  classify_task
  assess_query_privacy
  retrieve_notes
  calculate_effective_privacy
  select_model_profile
  build_context
  generate_answer
  build_citations
  validate_citations
  format_structured_output
  finalize

For Batch 7 only the `research_memory` task type is supported. The graph
is intentionally linear (no conditional branches) — branching is added
when additional task types land.
"""

from __future__ import annotations

from typing import Any

from rdos.config import RdosConfig
from rdos.graph.state import ResearchGraphState
from rdos.llm.model_router import ModelRouter, RoutingInput
from rdos.llm.privacy_router import PrivacyInput, PrivacyRouter
from rdos.llm.provider import LLMAdapter, LLMMessage, StubLLMAdapter
from rdos.rag.citation_builder import CitationBuilder
from rdos.rag.citation_validator import CitationValidator
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.hybrid_search import RetrievalFilters
from rdos.rag.retriever import HybridRetriever
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore
from rdos.schemas.research import ResearchAnswer


class ResearchMemoryGraph:
    """Wraps the 11 nodes with explicit wiring (no LangGraph dependency yet).

    State flows through `run()` linearly. We intentionally avoid
    langgraph.StateGraph for this batch so we don't pull in checkpoint
    complexity; we'll port it once trace/resume requirements firm up.
    """

    def __init__(
        self,
        *,
        config: RdosConfig,
        sqlite_store: SqliteMetadataStore,
        vector_store: LanceVectorStore,
        embedding: EmbeddingProvider | None = None,
        llm: LLMAdapter | None = None,
    ) -> None:
        self.config = config
        self.store = sqlite_store
        self.vectors = vector_store
        self.embedding = embedding or build_embedding_provider(
            provider=config.models.embedding.provider,
            dim=config.models.embedding.dim or config.rag.embedding.dim,
        )
        self.llm = llm or StubLLMAdapter(model="stub", provider="stub")
        self.privacy_router = PrivacyRouter(config.privacy_policy)
        self.model_router = ModelRouter(config.models)

    # ----- node implementations -----

    def classify_task(self, state: ResearchGraphState) -> ResearchGraphState:
        state["task_type"] = "research_memory"
        return state

    def assess_query_privacy(self, state: ResearchGraphState) -> ResearchGraphState:
        query = state["user_query"]
        level = self.privacy_router.assess_query(query)
        state["query_privacy_level"] = level
        return state

    def retrieve_notes(self, state: ResearchGraphState) -> ResearchGraphState:
        retriever = HybridRetriever(
            sqlite_store=self.store,
            vector_store=self.vectors,
            embedding=self.embedding,
            config=self.config,
        )
        # Only retrieve public + private_summary chunks for cloud-friendly context.
        # We DO NOT pre-filter here; effective-privacy is computed afterwards.
        # This is deliberate: privacy is taken on what was actually retrieved.
        result = retriever.search(
            state["user_query"],
            top_k=self.config.rag.retrieval.top_k,
            filters=RetrievalFilters(),
        )
        state["retrieved_chunks"] = result.chunks
        state["retrieved_doc_ids"] = sorted({c.doc_id for c in result.chunks})
        return state

    def calculate_effective_privacy(self, state: ResearchGraphState) -> ResearchGraphState:
        decision = self.privacy_router.calculate_effective_privacy(
            PrivacyInput(
                user_query=state["user_query"],
                user_query_privacy=state["query_privacy_level"],
                retrieved_chunks=state.get("retrieved_chunks"),
            )
        )
        state["privacy_decision"] = decision
        state["effective_privacy_level"] = decision.effective_privacy_level
        return state

    def select_model_profile(self, state: ResearchGraphState) -> ResearchGraphState:
        routing = self.model_router.select(
            RoutingInput(
                task_type=state["task_type"],
                effective_privacy_level=state["effective_privacy_level"],
            )
        )
        state["model_routing"] = routing
        return state

    def build_context(self, state: ResearchGraphState) -> ResearchGraphState:
        chunks = state.get("retrieved_chunks") or []
        if not chunks:
            state["context"] = ""
            return state
        lines: list[str] = []
        for i, c in enumerate(chunks, 1):
            heading = " > ".join(c.heading_path) if c.heading_path else c.title
            lines.append(
                f"[{i}] {c.title} :: {heading}\n"
                f"chunk_id={c.chunk_id}\n"
                f"{c.chunk_text}\n"
            )
        state["context"] = "\n---\n".join(lines)
        return state

    def generate_answer(self, state: ResearchGraphState) -> ResearchGraphState:
        routing = state["model_routing"]
        system = (
            "You are a research-memory assistant. Answer the user's question using "
            "ONLY the provided context. If the context is insufficient, say so. "
            "Always cite chunks by their [N] index."
        )
        user = (
            f"Question: {state['user_query']}\n\n"
            f"Context:\n{state.get('context', '')}\n\n"
            f"Answer:"
        )
        try:
            resp = self.llm.generate(
                [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=user),
                ],
                max_tokens=routing.suggested_max_tokens,
                temperature=routing.suggested_temperature,
            )
            state["raw_answer"] = resp.text
        except Exception as exc:  # noqa: BLE001
            state["raw_answer"] = ""
            state.setdefault("errors", []).append(f"generate_answer: {exc!s}")
        return state

    def build_citations(self, state: ResearchGraphState) -> ResearchGraphState:
        chunks = state.get("retrieved_chunks") or []
        builder = CitationBuilder(max_citations=self.config.rag.retrieval.top_k)
        citations = builder.build(state["user_query"], _as_retrieval_result(chunks))
        state["citations"] = citations
        return state

    def validate_citations(self, state: ResearchGraphState) -> ResearchGraphState:
        validator = CitationValidator(self.store)
        report = validator.validate_many(
            state.get("citations") or [],
            state.get("retrieved_chunks") or [],
        )
        state["citation_report"] = report
        return state

    def format_structured_output(self, state: ResearchGraphState) -> ResearchGraphState:
        # We don't strictly need a real LLM call to format ResearchAnswer; build it locally.
        report = state.get("citation_report")
        all_valid = bool(report and report.all_valid)
        confidence = _confidence(state, all_valid)

        answer = ResearchAnswer(
            answer=state.get("raw_answer", ""),
            citations=state.get("citations") or [],
            confidence=confidence,
            selected_model_profile=state["model_routing"].selected_profile,
            effective_privacy_level=state["effective_privacy_level"],
            task_type=state["task_type"],
            structured_payload={
                "citation_valid": all_valid,
                "citation_count": len(state.get("citations") or []),
            },
        )
        state["final_answer"] = answer
        state["structured_payload"] = answer.structured_payload or {}
        state["confidence"] = confidence
        return state

    # ----- run loop -----

    def run(self, user_query: str) -> ResearchGraphState:
        state: ResearchGraphState = ResearchGraphState(
            user_query=user_query,
            errors=[],
        )
        for node in (
            self.classify_task,
            self.assess_query_privacy,
            self.retrieve_notes,
            self.calculate_effective_privacy,
            self.select_model_profile,
            self.build_context,
            self.generate_answer,
            self.build_citations,
            self.validate_citations,
            self.format_structured_output,
        ):
            state = node(state)
        return state


def _confidence(state: ResearchGraphState, all_valid: bool) -> float:
    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        return 0.1
    base = 0.5
    if all_valid:
        base += 0.2
    # Tie confidence to top retrieved score (chunk.score is in [0, 1] after RRF)
    top_score = max((c.score or 0.0) for c in chunks)
    base += min(0.2, top_score * 0.2)
    return min(0.99, base)


class _RetrievalResultShim:
    """Minimal stand-in so CitationBuilder can iterate chunks."""

    def __init__(self, chunks: list[Any]) -> None:
        self.chunks = chunks


def _as_retrieval_result(chunks: list[Any]) -> Any:
    return _RetrievalResultShim(chunks)


def build_research_memory_graph(
    *,
    config: RdosConfig | None = None,
    sqlite_store: SqliteMetadataStore | None = None,
    vector_store: LanceVectorStore | None = None,
    embedding: EmbeddingProvider | None = None,
    llm: LLMAdapter | None = None,
) -> ResearchMemoryGraph:
    """Build a fully wired graph with sensible defaults from config."""
    from rdos.config import get_config

    cfg = config or get_config()
    store = sqlite_store or SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = vector_store or LanceVectorStore(
        cfg.rag.storage.lancedb_path,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    return ResearchMemoryGraph(
        config=cfg,
        sqlite_store=store,
        vector_store=vectors,
        embedding=embedding,
        llm=llm,
    )
