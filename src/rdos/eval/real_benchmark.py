"""Real-corpus benchmark — embedding provider comparison + ask latency."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.retrieval_benchmark import benchmark_retrieval
from rdos.llm.provider import StubLLMAdapter
from rdos.rag.embedding import build_embedding_provider
from rdos.rag.storage_sqlite import SqliteMetadataStore
from rdos.rag.vector_store import LanceVectorStore


def measure_local_model_health(cfg: RdosConfig) -> dict[str, Any]:
    """Probe chat + embedding endpoints via the embedding provider health check."""
    from rdos.llm.local_llama_cpp import LocalLlamaCppAdapter

    out: dict[str, Any] = {}
    try:
        adapter = LocalLlamaCppAdapter.from_config(cfg.models, "local_fast")
        out["chat_health"] = adapter.health()
    except Exception as exc:  # noqa: BLE001
        out["chat_health"] = False
        out["chat_error"] = str(exc)[:200]
    try:
        dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
        emb = build_embedding_provider("local-bge-m3", dim=dim)
        from rdos.rag.embedding import OpenAICompatibleEmbeddingProvider

        if isinstance(emb, OpenAICompatibleEmbeddingProvider):
            out["embedding_health"] = emb.health()
        else:
            out["embedding_health"] = "n/a (provider not local)"
    except Exception as exc:  # noqa: BLE001
        out["embedding_health"] = False
        out["embedding_error"] = str(exc)[:200]
    return out


def measure_ask_latency(
    cfg: RdosConfig,
    *,
    queries: list[str] | None = None,
    embedding_provider: str | None = None,
) -> dict[str, Any]:
    """Measure end-to-end ask latency using a stub LLM (isolates retrieval cost)."""
    from rdos.graph.langgraph_runtime import build_langgraph_runtime

    queries = queries or [
        "GraphRAG VectorRAG 層次化摘要",
        "AgentTrace 多智能體因果圖追蹤",
        "Argus LLM 六維度輸出評估框架",
    ]
    latencies: list[int] = []
    sample_outputs: list[dict[str, Any]] = []
    store = SqliteMetadataStore(cfg.rag.storage.sqlite_path)
    dim = cfg.models.embedding.dim or cfg.rag.embedding.dim
    vectors = LanceVectorStore(cfg.rag.storage.lancedb_path, dim=dim)
    emb = build_embedding_provider(embedding_provider or cfg.models.embedding.provider, dim=dim)
    runtime = build_langgraph_runtime(
        config=cfg, sqlite_store=store, vector_store=vectors, embedding=emb, llm=StubLLMAdapter()
    )
    for q in queries:
        started = time.perf_counter()
        try:
            state, _ = runtime.invoke(q)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            latencies.append(elapsed_ms)
            fa = state.get("final_answer")
            sample_outputs.append(
                {
                    "query": q,
                    "latency_ms": elapsed_ms,
                    "citation_count": len(state.get("citations") or []),
                    "answer_chars": len(fa.answer if fa else ""),
                }
            )
        except Exception as exc:  # noqa: BLE001
            sample_outputs.append({"query": q, "error": str(exc)[:200]})
    store.close()
    latencies.sort()
    return {
        "samples": len(latencies),
        "ask_latency_p50_ms": latencies[len(latencies) // 2] if latencies else 0,
        "ask_latency_p95_ms": latencies[-1] if latencies else 0,
        "samples_detail": sample_outputs,
    }


def benchmark_all(
    cfg: RdosConfig,
    *,
    embedding_provider: str | None = None,
    eval_set: str | Path = "eval_sets/real_rag_qa.jsonl",
) -> dict[str, Any]:
    retrieval = benchmark_retrieval(
        cfg, embedding_provider=embedding_provider, eval_set=eval_set
    )
    ask = measure_ask_latency(cfg, embedding_provider=embedding_provider)
    health = measure_local_model_health(cfg)
    return {
        "embedding_provider": embedding_provider or cfg.models.embedding.provider,
        "retrieval": retrieval,
        "ask_latency": ask,
        "local_model_health": health,
    }


def write_benchmark_report(payload: dict[str, Any], out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# RDOS Benchmark Report", ""]
    lines.append(f"_Embedding provider: {payload.get('embedding_provider', '?')}_")
    lines.append("")
    lines.append("## Local model health")
    lines.append("")
    lines.append("| Probe | Result |")
    lines.append("| --- | --- |")
    health = payload.get("local_model_health") or {}
    for k, v in health.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Retrieval")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    retrieval = payload.get("retrieval") or {}
    for k, v in retrieval.items():
        if k == "results":
            continue
        if isinstance(v, float):
            lines.append(f"| {k} | {v:.4f} |")
        else:
            lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Ask latency (stub LLM)")
    lines.append("")
    ask = payload.get("ask_latency") or {}
    for k, v in ask.items():
        if k == "samples_detail":
            continue
        lines.append(f"- {k}: {v}")
    lines.append("")
    if ask.get("samples_detail"):
        lines.append("## Per-query ask samples")
        lines.append("")
        lines.append("| Query | Latency (ms) | Citations | Answer chars |")
        lines.append("| --- | --- | --- | --- |")
        for s in ask["samples_detail"]:
            if "error" in s:
                lines.append(f"| {s['query']} | (error) | - | - |")
            else:
                lines.append(
                    f"| {s['query']} | {s['latency_ms']} | {s['citation_count']} | {s['answer_chars']} |"
                )
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
