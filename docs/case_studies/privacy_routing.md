# Case Study — Privacy Routing

> Effective privacy is the strictest level across **all** input sources, not just the query.

## The problem

Naive privacy routers look only at the query. That misses the case where a `public` query retrieves a `company_sensitive` chunk and then ships both to a cloud model.

## The RDOS rule

```
effective_privacy = max(
    user_query_privacy,
    retrieved_chunk_privacy_levels,
    tool_result_privacy_level,
    memory_context_privacy_level,
    trace_context_privacy_level,
)
```

Order (low → high): `public < private_summary < private_raw < company_sensitive`.

## What each level permits

| Level | External model? | Confirmation? |
| --- | --- | --- |
| public | yes | no |
| private_summary | yes | **yes** (escalation needs confirmation) |
| private_raw | **no** | no |
| company_sensitive | **no** | no |

## The implementation

`PrivacyRouter.calculate_effective_privacy(...)` returns a `PrivacyDecision` that captures every input level *and* the final effective level, so the trace can show exactly why a run was classified as it was:

```json
{
  "user_query_privacy": "public",
  "retrieved_chunk_privacies": ["public", "company_sensitive"],
  "effective_privacy_level": "company_sensitive",
  "allows_external_model": false,
  "reason": "effective=company_sensitive query=public chunks_strictest=company_sensitive rank=3"
}
```

## Hard guarantees

- `private_raw` and `company_sensitive` runs **never** set `allows_external_model = true`.
- `private_summary` runs that escalate to cloud **always** set `requires_user_confirmation = true`.
- These guarantees are encoded in `eval_sets/privacy_routing.jsonl` and gated to 100% compliance in the release gate.

## Leakage metrics

Two hard-zero metrics in the release gate:

- `private_raw_leakage_rate = 0`
- `company_sensitive_leakage_rate = 0`

Any non-zero value is an automatic release-gate FAIL, regardless of other metrics.

## Query privacy classification

Today the router uses a small keyword hint table from `configs/privacy_policy.yaml`:

```yaml
query_privacy_hints:
  company_sensitive:
    - internal
    - confidential
    - salary
    - roadmap
```

This is deliberately conservative — a real classifier (small fine-tuned model or LLM-as-judge) drops in later. The keyword fallback keeps the system safe by defaulting to `private_raw` for unknown queries.
