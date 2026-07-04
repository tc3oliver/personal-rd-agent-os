# Case Study — Resume Positioning

> How to talk about RDOS in an interview.

## One-liner

> "A model-agnostic, privacy-aware personal R&D agent: Markdown notes → hybrid retrieval → cited answers, with effective-privacy-driven model routing and a release-gated eval harness."

## The five things to highlight

### 1. Privacy-aware model routing

Most agent demos hard-code "use GPT-4." RDOS computes effective privacy across query, retrieved chunks, tool results, memory, and trace context, then forces local-only execution when the level is `private_raw` or `company_sensitive`. Cloud escalation for `private_summary` requires explicit user confirmation.

**Interview hook**: "Show me another open-source agent that does privacy-aware routing with hard leakage gates."

### 2. Citation grounding, validated

Every answer is backed by citations that pass a three-way check: `chunk_exists ∧ hash_matches ∧ in_retrieved_context`. Hallucinated references are caught at validation time, not at user-trust time.

**Interview hook**: "If the model invents a chunk_id, the validator catches it. If it cites a real chunk it wasn't shown, the validator catches that too."

### 3. Model-agnostic by construction

The `ModelRouter` returns data only — never a callable tool-bound model. This is a load-bearing constraint that prevents privacy leakage and keeps the adapter swappable.

**Interview hook**: "Show me where `bind_tools` is called in the router. It isn't, and that's the point."

### 4. Evaluation-driven

A release gate (RAG recall@5, citation accuracy, model routing correctness, privacy leakage) decides whether the project ships. Two leakage metrics are pinned at zero.

**Interview hook**: "I can't ship if leakage > 0. That's not a vibe, it's a test."

### 5. Operable

Every run writes a self-contained JSONL trace. `rdos trace list` and `rdos trace show <run_id>` give post-hoc forensics. Re-indexing is idempotent by `chunk_hash`.

**Interview hook**: "If something goes wrong, I have the run_id. The trace tells me exactly what privacy decision was made and what was retrieved."

## Things to NOT claim

- "Production-ready." It's a portfolio piece. Be honest.
- "Beats GPT-4." No, the local model is for privacy, not capability.
- "Solves hallucination." It catches *citation* hallucination. Answer hallucination is still upstream.

## Sample behavioral STAR answers

**Q: Tell me about a time you designed a system with hard constraints.**

> "I built a personal R&D agent with a hard constraint: `private_raw` data can never reach a cloud model. The constraint shaped three layers — the PrivacyRouter computes effective privacy across all input sources, the ModelRouter force-downgrades cloud selections, and the release gate fails on any non-zero leakage. The constraint was the design, not a feature."

**Q: How do you handle ambiguous requirements?**

> "I write them as data. The privacy level of an unknown query defaults to `private_raw` — the safe choice. The keyword hint table lives in YAML, not code, so the policy can change without a deploy. And the eval harness checks the policy against 10 known cases every release."

## Talking points by audience

| Audience | Lead with |
| --- | --- |
| Backend / infra | Privacy router + idempotent indexer + JSONL trace |
| ML / AI eng | Hybrid retrieval (RRF), structured output retry, eval harness |
| Product | "Personal R&D agent that never leaks your private notes" |
| Security | Effective privacy across all input sources + hard leakage gates |
