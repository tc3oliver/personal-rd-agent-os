# Case Study — Model Routing

> How RDOS picks the right model profile without binding tools at the router layer.

## The problem

Most agent frameworks couple "which model" with "what tools" by returning a pre-bound `ChatModel` object from the router. That coupling has three failure modes:

1. **Privacy leakage**: the bound model may be a cloud model, but the router doesn't know the privacy level yet.
2. **Test fragility**: tests must mock the entire LLM stack just to verify the routing decision.
3. **Swap friction**: moving from local llama.cpp to a cloud provider requires touching the router.

## The RDOS rule

> `ModelRouter.select(...)` returns a **`ModelRoutingDecision`** — pure data. Never a callable model.

```python
@dataclass
class ModelRoutingDecision:
    selected_profile: str
    provider: str         # "local" | "cloud"
    model_name: str
    allows_external_model: bool
    requires_user_confirmation: bool
    ...
```

The orchestrator reads the decision, then constructs the right `LLMAdapter`. Today only `local_fast` (local llama.cpp) and `cloud_reasoning` (any OpenAI-compatible cloud) are wired.

## The decision tree

```
1. Risk override: high risk × (private_raw | company_sensitive) → local_fast
2. Privacy hard gate: private_raw | company_sensitive → local_fast
3. Task default lookup (e.g. research_synthesis → cloud_reasoning)
4. Fallback: local_fast
```

After the profile is chosen, `allows_external_model` is **computed from `provider`**, not stored as a separate fact — so it cannot drift from the actual provider.

## The four test cases that must pass

| Task | Privacy | Expected profile | Confirmation |
| --- | --- | --- | --- |
| research_synthesis | public | cloud_reasoning | false |
| research_memory | private_raw | local_fast | false |
| code_analysis | company_sensitive | local_fast (forced down) | false |
| research_synthesis | private_summary | cloud_reasoning | **true** |

These are encoded in `eval_sets/model_routing.jsonl` and run as part of the release gate.

## Why no `bind_tools`

Tool binding happens later, at the orchestrator layer, only after:
- Privacy has been computed.
- The model has been selected.
- The `tool_policy.yaml` gate has approved the tool for this privacy level.

Putting `bind_tools` in the router would force the router to know about every tool's privacy eligibility — a layering violation.
