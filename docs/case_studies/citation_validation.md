# Case Study — Citation Validation

> Citations are checked against the store AND the retrieved context, so hallucinated references are caught.

## The problem

A naive citation system trusts the LLM: whatever chunk_id the model emits becomes the citation. That fails in two ways:

1. **Hallucinated chunk_ids** — the model invents an ID that doesn't exist.
2. **Hash drift** — the model remembers a chunk_id from a previous run, but the underlying chunk has been re-indexed and its hash changed.
3. **Out-of-context citations** — the model cites a chunk it wasn't shown, which defeats the purpose of RAG.

## The RDOS rule

A citation is valid iff:

```
chunk_exists ∧ hash_matches ∧ in_retrieved_context
```

| Check | What it catches |
| --- | --- |
| `chunk_exists` | Hallucinated chunk_ids that aren't in the store |
| `hash_matches` | Stale references after a re-index |
| `in_retrieved_context` | LLM citing chunks it wasn't given (defeats RAG grounding) |

## The implementation

```python
class CitationValidator:
    def validate(self, citation, retrieved_chunks) -> CitationValidationResult:
        chunk = self.store.get_chunk(citation.chunk_id)
        chunk_exists = chunk is not None
        hash_matches = bool(chunk) and chunk.chunk_hash == citation.chunk_hash
        retrieved_ids = {c.chunk_id for c in retrieved_chunks}
        in_retrieved = citation.chunk_id in retrieved_ids
        ...
```

`CitationReport` aggregates the per-citation results with `all_valid`, `valid_count`, `total_count`.

## Release gate

Two citation metrics:

| Metric | Target |
| --- | --- |
| `citation_accuracy` | ≥ 0.70 |
| `valid_chunk_reference_rate` | ≥ 0.95 |

The first measures "did we cite the right doc?" The second measures "are the citations we did make valid?" The two are independent — a system can be accurate but reference-invalid (e.g. by citing from memory) or reference-valid but inaccurate (e.g. by citing the wrong chunk from the right doc).

## Why this matters for the resume

Citation validation is the difference between "RAG demo" and "RAG you could ship." The three-way check (`exists ∧ hash_matches ∧ in_context`) is small to implement but easy to forget; calling it out as a first-class design constraint signals engineering maturity.
