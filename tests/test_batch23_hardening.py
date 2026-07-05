"""Tests for Batch 23 — v0.2.1 Trust Runtime Hardening (audit P0/P1 fixes)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rdos.llm.cloud_send import (
    CloudSendResult,
    PrivacyBlockError,
    cloud_send,
    cloud_send_or_raise,
)
from rdos.llm.prompt_privacy_validator import validate_prompt
from rdos.llm.provider import LLMMessage

# ---- P0-1: rdos thread registered in main CLI ----


def test_thread_app_registered_in_main_cli() -> None:
    """rdos --help must list thread (was missing in v0.2.0)."""
    from rdos.cli import app as main_app

    names = set()
    for info in main_app.registered_groups:
        names.add(info.name)
    for cmd in main_app.registered_commands:
        names.add(cmd.name)
    assert "thread" in names, f"thread not in main CLI: {sorted(names)}"


def test_thread_subcommands_present() -> None:
    from rdos.cli.thread import app as thread_app

    names = {cmd.name for cmd in thread_app.registered_commands}
    for expected in ("new", "ask", "list", "show", "close"):
        assert expected in names, f"missing rdos thread subcommand: {expected}"


# ---- P0-2: runtime files untracked ----


def test_no_runtime_db_in_git_tracking() -> None:
    """data/approvals.db / data/threads.db / data/checkpoints.db must not be git-tracked."""
    import subprocess

    here = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "ls-files", "data/"],
        cwd=here,
        capture_output=True,
        text=True,
        check=False,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    forbidden = {"data/approvals.db", "data/threads.db", "data/checkpoints.db"}
    offenders = forbidden & set(files)
    assert not offenders, f"runtime DBs still tracked: {sorted(offenders)}"


def test_no_synthesis_report_in_git_tracking() -> None:
    """data/generated/reports/synthesis_*.md must not be git-tracked (runtime output)."""
    import subprocess

    here = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "ls-files", "data/generated/"],
        cwd=here,
        capture_output=True,
        text=True,
        check=False,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert not any("synthesis_" in f for f in files), (
        f"runtime synthesis reports still tracked: {files}"
    )


# ---- P1-2: cloud_send shim makes validator live ----


def test_cloud_send_blocks_pii() -> None:
    msgs = [LLMMessage(role="user", content="email alice@example.com for details")]
    result = cloud_send(msgs)
    assert isinstance(result, CloudSendResult)
    assert result.blocked is True
    assert result.validation.n_violations >= 1
    assert "unredacted" in result.reason or "recognition" in result.reason


def test_cloud_send_or_raise_raises_on_pii() -> None:
    msgs = [LLMMessage(role="user", content="phone 0912345678")]
    with pytest.raises(PrivacyBlockError):
        cloud_send_or_raise(msgs)


def test_cloud_send_allows_clean_prompt() -> None:
    msgs = [LLMMessage(role="user", content="what is GraphRAG?")]
    val = cloud_send_or_raise(msgs)
    assert val.allowed is True
    assert val.n_violations == 0


def test_cloud_send_aggregates_multi_message() -> None:
    """Combined messages — PII in any message blocks the call."""
    msgs = [
        LLMMessage(role="system", content="be helpful"),
        LLMMessage(role="user", content="contact me at alice@example.com"),
    ]
    result = cloud_send(msgs)
    assert result.blocked is True


def test_validate_prompt_still_works_directly() -> None:
    """Direct API still works for tests / debug."""
    val = validate_prompt("id A123456789 here")
    assert val.allowed is False
    val2 = validate_prompt("clean query")
    assert val2.allowed is True


# ---- P1-4 + P1-5: retrieval knobs in rag.yaml ----


def test_rag_yaml_exposes_no_answer_threshold() -> None:
    """no_answer_threshold must be explicit in configs/rag.yaml (audit P1-4)."""
    here = Path(__file__).resolve().parent.parent
    yaml_text = (here / "configs" / "rag.yaml").read_text(encoding="utf-8")
    assert "no_answer_threshold:" in yaml_text, (
        "no_answer_threshold not surfaced in configs/rag.yaml"
    )


def test_rag_yaml_exposes_retrieval_knobs() -> None:
    """Batch 13 retrieval knobs must be in configs/rag.yaml (audit P1-5)."""
    here = Path(__file__).resolve().parent.parent
    yaml_text = (here / "configs" / "rag.yaml").read_text(encoding="utf-8")
    for knob in (
        "vector_top_k",
        "keyword_top_k",
        "rerank_top_k",
        "min_score_threshold",
        "enable_query_rewrite",
    ):
        assert f"{knob}:" in yaml_text, f"{knob} not surfaced in configs/rag.yaml"


def test_config_loader_reads_rag_yaml_knobs() -> None:
    """RdosConfig must pick up the explicit yaml values (not just code defaults)."""
    from rdos.config import load_config

    here = Path(__file__).resolve().parent.parent
    cfg = load_config(here / "configs")
    assert cfg.rag.retrieval.no_answer_threshold == 0.0
    assert cfg.rag.retrieval.vector_top_k == 20
    assert cfg.rag.retrieval.enable_query_rewrite is True


# ---- P1-3: docs refreshed ----


def test_limitations_doc_acknowledges_trace_redaction_done() -> None:
    """limitations.md must NOT still say trace redaction is future work."""
    here = Path(__file__).resolve().parent.parent
    text = (here / "docs" / "limitations.md").read_text(encoding="utf-8")
    assert "implemented (Batch 18.5)" in text.lower() or "implemented" in text.lower()
    # Stale phrase removed
    assert "fix lands in batch 18.5" not in text.lower()


def test_v0_2_release_notes_acknowledge_infra_only_cloud() -> None:
    here = Path(__file__).resolve().parent.parent
    text = (
        here / "docs" / "release_notes" / "v0.2.0-trust-runtime.md"
    ).read_text(encoding="utf-8")
    assert "infra-only" in text.lower() or "not shipped" in text.lower() or "intentionally not shipped" in text.lower()


def test_v0_2_1_release_notes_exist() -> None:
    here = Path(__file__).resolve().parent.parent
    assert (here / "docs" / "release_notes" / "v0.2.1-trust-runtime-hardened.md").exists()
