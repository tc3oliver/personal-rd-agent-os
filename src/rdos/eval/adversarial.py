"""Adversarial eval aggregator — wires `*_adversarial.jsonl` into eval all.

Each adversarial set is run by its corresponding evaluator with the
adversarial file as the eval_set. Returns aggregated metrics matching
the baseline evaluator's schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdos.config import RdosConfig
from rdos.eval.citation_eval import evaluate_citation
from rdos.eval.model_routing_eval import evaluate_model_routing
from rdos.eval.privacy_eval import evaluate_privacy


def _exists(path: str | Path) -> bool:
    return Path(path).exists()


def evaluate_citation_adversarial(cfg: RdosConfig) -> dict[str, Any]:
    path = "eval_sets/citation_adversarial.jsonl"
    if not _exists(path):
        return {"skipped": True, "reason": f"{path} not found", "metrics": {}}
    return evaluate_citation(cfg, eval_set=path)


def evaluate_model_routing_adversarial(cfg: RdosConfig) -> dict[str, Any]:
    path = "eval_sets/model_routing_adversarial.jsonl"
    if not _exists(path):
        return {"skipped": True, "reason": f"{path} not found", "value": 0.0}
    return evaluate_model_routing(cfg, eval_set=path)


def evaluate_privacy_adversarial(cfg: RdosConfig) -> dict[str, Any]:
    path = "eval_sets/privacy_routing_adversarial.jsonl"
    if not _exists(path):
        return {"skipped": True, "reason": f"{path} not found", "metrics": {}}
    return evaluate_privacy(cfg, eval_set=path)
