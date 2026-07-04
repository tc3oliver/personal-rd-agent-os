"""Citation eval — accuracy + valid-chunk-reference rate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.rag_eval import load_jsonl
from rdos.graph.research_memory_graph import ResearchMemoryGraph
from rdos.llm.provider import LLMAdapter, StubLLMAdapter
from rdos.rag.embedding import EmbeddingProvider, build_embedding_provider
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


def evaluate_citation(
    cfg: RdosConfig,
    *,
    eval_set: str | Path = "eval_sets/citation.jsonl",
    embedding: EmbeddingProvider | None = None,
    llm: LLMAdapter | None = None,
) -> dict[str, Any]:
    samples = load_jsonl(eval_set)
    if not samples:
        return {
            "metrics": {
                "citation_accuracy": 0.0,
                "valid_chunk_reference_rate": 0.0,
            },
            "samples": 0,
            "results": [],
        }

    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    vectors = LanceVectorStore(
        cfg.rag.storage.lancedb_path,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    emb = embedding or build_embedding_provider(
        provider=cfg.models.embedding.provider,
        dim=cfg.models.embedding.dim or cfg.rag.embedding.dim,
    )
    used_llm = llm or StubLLMAdapter()
    graph = ResearchMemoryGraph(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=used_llm
    )

    accurate = 0
    valid_refs = 0
    total_citations = 0
    results: list[dict[str, Any]] = []

    for sample in samples:
        state = graph.run(sample["query"])
        citations = state.get("citations") or []
        report = state.get("citation_report")
        expected_docs = set(sample.get("expected_doc_ids", []))
        must_cite = sample.get("must_cite_at_least", 1)

        cited_docs = {c.file_path for c in citations}
        # "Accuracy" = cited at least `must_cite` chunks from expected docs
        correct_citations = len(cited_docs & expected_docs)
        is_accurate = correct_citations >= must_cite and len(citations) >= must_cite
        accurate += int(is_accurate)

        valid_in_run = (
            sum(1 for r in report.results if r.is_valid) if report is not None else 0
        )
        if citations:
            valid_refs += valid_in_run
            total_citations += len(citations)

        results.append(
            {
                "query": sample["query"],
                "expected_doc_ids": sorted(expected_docs),
                "cited_doc_ids": sorted(cited_docs),
                "citation_count": len(citations),
                "valid_in_run": valid_in_run,
                "accurate": is_accurate,
            }
        )

    store.close()
    citation_accuracy = accurate / len(samples)
    valid_chunk_reference_rate = (valid_refs / total_citations) if total_citations else 0.0

    return {
        "metrics": {
            "citation_accuracy": citation_accuracy,
            "valid_chunk_reference_rate": valid_chunk_reference_rate,
        },
        "samples": len(samples),
        "results": results,
    }
