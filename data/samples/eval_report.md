# Sample Eval Report

This is a sample of what `data/reports/eval_report.md` looks like after `rdos eval all` runs against the synthetic sample set.

> This file is a snapshot for documentation. The live report is regenerated on every `rdos eval all` run.

## Release Gate

| Metric | Value | Target | Status |
| --- | --- | --- | --- |
| rag_recall_at_5 | 0.8000 | gte 0.75 | PASS (>= 0.75) |
| citation_accuracy | 0.8000 | gte 0.70 | PASS (>= 0.70) |
| valid_chunk_reference_rate | 1.0000 | gte 0.95 | PASS (>= 0.95) |
| structured_output_json_validity | 1.0000 | gte 0.95 | PASS (>= 0.95) |
| model_routing_correct_rate | 1.0000 | gte 0.85 | PASS (>= 0.85) |
| privacy_policy_compliance | 1.0000 | eq 1.00 | PASS (= 1.00) |
| private_raw_leakage_rate | 0.0000 | eq 0.00 | PASS (= 0.00) |
| company_sensitive_leakage_rate | 0.0000 | eq 0.00 | PASS (= 0.00) |

**Verdict: PASS**

## How each metric is computed

- **rag_recall_at_5**: fraction of queries where at least one expected doc appears in the top-5 retrieved docs.
- **citation_accuracy**: fraction of queries where the citation set includes at least `must_cite_at_least` chunks from expected docs.
- **valid_chunk_reference_rate**: across all citations produced, the fraction that pass `chunk_exists ∧ hash_matches ∧ in_retrieved_context`.
- **structured_output_json_validity**: 1.0 if `ResearchAnswer` always serializes to valid JSON (currently a deterministic formatter).
- **model_routing_correct_rate**: fraction of model_routing eval samples where the chosen profile, provider, and confirmation flag all match expected.
- **privacy_policy_compliance**: fraction of privacy_routing eval samples where effective privacy, allows_external_model, and must_local constraints all hold.
- **private_raw_leakage_rate**: fraction of samples where effective privacy is `private_raw` AND `allows_external_model` is true. Must be 0.
- **company_sensitive_leakage_rate**: same, but for `company_sensitive`. Must be 0.

## Adding a new metric

1. Add the metric name + op + threshold to `RELEASE_GATE` in `src/rdos/eval/report.py`.
2. Add a fixture to `eval_sets/<name>.jsonl`.
3. Add an evaluator under `src/rdos/eval/<name>_eval.py` returning `{"metric": ..., "value": ..., "results": ...}`.
4. Wire it into `rdos eval <name>` and the `_run_all()` function in `src/rdos/cli/eval.py`.
