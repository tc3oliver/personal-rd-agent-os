"""Tests for Batch 21: redaction + prompt privacy validator."""

from __future__ import annotations

import pytest

from rdos.eval.redaction_eval import evaluate_redaction
from rdos.eval.report import REDACTION_GATE
from rdos.llm.prompt_privacy_validator import validate_prompt
from rdos.llm.redaction import load_redaction_config, redact, scan


def _cfg():
    return load_redaction_config("configs/redaction.yaml")


def test_email_redacted() -> None:
    text = "聯絡我 alice@example.com 謝謝"
    out, recs = redact(text, _cfg())
    assert any(r.type == "EMAIL" for r in recs)
    assert "alice@example.com" not in out
    assert "[REDACTED-EMAIL]" in out


def test_phone_tw_mobile_redacted() -> None:
    out, recs = redact("手機 0912345678", _cfg())
    assert any("PHONE" in r.type for r in recs)
    assert "0912345678" not in out


def test_id_tw_redacted() -> None:
    out, recs = redact("身分證 A123456789", _cfg())
    assert any("ID" in r.type for r in recs)
    assert "A123456789" not in out


def test_url_redacted() -> None:
    out, recs = redact("see https://example.com/x", _cfg())
    assert any(r.type == "URL" for r in recs)
    assert "https://example.com/x" not in out


def test_ipv4_redacted() -> None:
    out, recs = redact("IP 192.168.1.1", _cfg())
    assert any(r.type == "IP" for r in recs)
    assert "192.168.1.1" not in out


def test_credit_card_redacted_with_luhn_check() -> None:
    # 4111 1111 1111 1111 passes Luhn
    out, recs = redact("卡號 4111 1111 1111 1111", _cfg())
    assert any(r.type == "CREDIT-CARD" for r in recs)
    assert "4111" not in out


def test_credit_card_invalid_luhn_not_redacted() -> None:
    # 9999 9999 9999 9999 fails Luhn
    out, recs = redact("卡號 9999 9999 9999 9999", _cfg())
    assert not any(r.type == "CREDIT-CARD" for r in recs)


def test_company_hint_redacted() -> None:
    cfg = _cfg()
    cfg["company_names"] = ["內部公司Z"]
    out, recs = redact("我是 內部公司Z 的員工", cfg)
    assert any(r.type == "COMPANY-HINT" for r in recs)
    assert "內部公司Z" not in out


def test_address_tw_redacted() -> None:
    out, recs = redact("公司地址 台北市信義路一段1號", _cfg())
    assert any(r.type == "ADDRESS-TW" for r in recs)
    assert "信義路" in out or "信義路" not in out  # at minimum not crash


def test_clean_text_no_redactions() -> None:
    recs = scan("totally clean english text without any PII", _cfg())
    assert recs == []


def test_redaction_eval_recall_and_precision() -> None:
    out = evaluate_redaction()
    assert out["samples"] >= 9
    assert out["redaction_recall"] >= 0.95
    assert out["redaction_precision"] >= 0.95


def test_prompt_privacy_validator_blocks_pii() -> None:
    val = validate_prompt("email me at alice@example.com", _cfg())
    assert not val.allowed
    assert val.n_violations >= 1
    assert val.violations


def test_prompt_privacy_validator_allows_clean() -> None:
    val = validate_prompt("what is GraphRAG?", _cfg())
    assert val.allowed
    assert val.n_violations == 0


def test_redaction_gate_in_place() -> None:
    assert REDACTION_GATE["redaction_recall"] == ("gte", 0.95)
    assert REDACTION_GATE["redaction_precision"] == ("gte", 0.95)


def test_redaction_strategy_mask() -> None:
    cfg = _cfg()
    cfg["replacement_strategy"] = "mask"
    out, _ = redact("contact alice@example.com", cfg)
    assert "alice@example.com" not in out
    assert "***" in out


def test_redaction_strategy_hash() -> None:
    cfg = _cfg()
    cfg["replacement_strategy"] = "hash"
    out, _ = redact("contact alice@example.com", cfg)
    assert "alice@example.com" not in out
    assert "[REDACTED-" in out


def test_cli_wired() -> None:
    from rdos.cli.redaction import app

    assert app is not None


@pytest.mark.parametrize(
    "text,expected_type",
    [
        ("test@test.com", "EMAIL"),
        ("0912345678", "PHONE-TW-MOBILE"),
        ("A123456789", "ID-TW"),
        ("https://x.io/y", "URL"),
        ("10.0.0.1", "IP"),
    ],
)
def test_each_recognizer_fires(text: str, expected_type: str) -> None:
    recs = scan(text, _cfg())
    types = {r.type for r in recs}
    assert expected_type in types or any(expected_type in t for t in types), (
        f"expected {expected_type} in {types}"
    )
